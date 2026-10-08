"""Phase 7 real persisted contracts, migration and concurrency; no provider calls."""
import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from app.models.schemas import HRReviewSubmissionInput, HRReviewDecisionInput
from app.storage.database import repository, SCHEMA_VERSION
from app.storage import models as dbm
from app.storage.hiring import HiringError
from app.security.rbac import AuthorizationError
from test_hiring import context, create, sources


def role(ctx, name):
    repository.assign_organization_human_role(workspace_id=ctx[3]['id'], target_user_id=ctx[1]['id'],
        human_role=name, actor_user_id=ctx[1]['id'])


def identity(ctx):
    return dict(workspace_id=ctx[3]['id'], user_id=ctx[1]['id'])


def draft(ctx):
    _, _, payload = sources(ctx[0])
    return create(ctx[0], 'job-descriptions', payload)


def submit(ctx, jd=None):
    jd = jd or draft(ctx)
    return repository.submit_review(HRReviewSubmissionInput(job_description={'id': jd['id'], 'revision': jd['revision']}), **identity(ctx))


def decide(ctx, record, action, approval=False):
    return repository.decide_review(record.id, HRReviewDecisionInput(expected_version=record.version,
        decision=action, notes='Human assessment of exact submitted material'), approval=approval, **identity(ctx))


def test_pinned_sources_submission_and_history(context):
    jd = draft(context)
    original = submit(context, jd)
    role(context, 'hr_reviewer'); role(context, 'hr_approver')
    reviewed = decide(context, original, 'recommend')
    approved = decide(context, reviewed, 'approve', True)
    assert approved.status == 'approved' and approved.version == 3
    assert [e.from_status for e in approved.history] == ['draft', 'pending_review', 'reviewed']
    assert [e.to_status for e in approved.history] == ['pending_review', 'reviewed', 'approved']
    assert all(e.actor_user_id == context[1]['id'] and e.occurred_at for e in approved.history)
    assert approved.job_description.model_dump(mode='json', by_alias=True) == jd
    source = approved.requirement
    repository.save_hiring('requirements', source.content.model_copy(update={'title': 'Updated requirement'}),
        record_id=source.id, expected_revision=1, **identity(context))
    assert repository.get_review(original.id, **identity(context)).requirement == source
    assert repository.get_hiring('job_descriptions', jd['id'], **identity(context)).revision == 1
    repository.initialize()
    assert repository.get_review(original.id, **identity(context)) == approved


@pytest.mark.parametrize('action,approval', [('approve', False), ('approve', True), ('recommend', True)])
def test_approval_requires_review_eligibility(context, action, approval):
    role(context, 'hr_approver')
    record = submit(context)
    with pytest.raises(HiringError) as conflict:
        decide(context, record, action, approval)
    assert conflict.value.status_code == 409
    assert len(repository.get_review(record.id, **identity(context)).history) == 1


@pytest.mark.parametrize('terminal,approval', [('request_changes', False), ('reject', False), ('request_changes', True), ('reject', True), ('approve', True)])
def test_terminal_decisions_revision_resubmission_and_no_transfer(context, terminal, approval):
    role(context, 'hr_reviewer'); role(context, 'hr_approver')
    jd = draft(context); first = submit(context, jd)
    if approval: first = decide(context, first, 'recommend')
    first = decide(context, first, terminal, approval)
    with pytest.raises(HiringError): decide(context, first, terminal, approval)
    with pytest.raises(HiringError): submit(context, jd)
    changed = repository.save_hiring('job_descriptions', first.job_description.content.model_copy(update={'summary': 'Human revision'}),
        record_id=jd['id'], expected_revision=1, **identity(context))
    second = submit(context, changed.model_dump(mode='json', by_alias=True))
    assert second.status == 'pending_review' and second.version == 1 and second.id != first.id
    historical = repository.get_review(first.id, **identity(context))
    assert historical.stale and historical.status == first.status
    assert historical.job_description.revision == 1 and second.job_description.revision == 2
    assert historical.history == first.history


@pytest.mark.parametrize('review_first', [False, True])
def test_changed_or_archived_jd_blocks_old_decisions(context, review_first):
    role(context, 'hr_reviewer'); role(context, 'hr_approver')
    record = submit(context)
    if review_first: record = decide(context, record, 'recommend')
    repository.save_hiring('job_descriptions', record.job_description.content.model_copy(update={'status': 'archived'}),
        record_id=record.job_description.id, expected_revision=1, **identity(context))
    with pytest.raises(HiringError): decide(context, record, 'approve' if review_first else 'recommend', review_first)
    with pytest.raises(HiringError): repository.submit_review(HRReviewSubmissionInput(job_description={'id': record.job_description.id, 'revision': 2}), **identity(context))


@pytest.mark.parametrize('table', [dbm.hr_review_submissions, dbm.hr_review_events])
@pytest.mark.parametrize('action', ['update', 'delete'])
def test_audit_history_is_database_immutable(context, table, action):
    submit(context)
    with pytest.raises(IntegrityError):
        with repository.engine.begin() as conn:
            conn.execute(delete(table) if action == 'delete' else update(table).values(id='rewritten'))


def test_concurrent_decisions_only_one_is_saved(context):
    role(context, 'hr_reviewer')
    record = submit(context)
    def attempt():
        try: return decide(context, record, 'recommend').status
        except HiringError as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results, key=str) == sorted(['reviewed', 409], key=str)
    assert len(repository.get_review(record.id, **identity(context)).history) == 2


def test_database_rejects_skipped_review_event(context):
    record = submit(context)
    with pytest.raises(IntegrityError):
        with repository.engine.begin() as conn:
            conn.execute(insert(dbm.hr_review_events).values(id='fake', workspace_id=context[3]['id'],
                submission_id=record.id, version=3, actor_user_id=context[1]['id'], occurred_at='now',
                action='approve', from_status='reviewed', to_status='approved', notes='Forged review'))


def test_v12_additive_migration_preserves_hr_sources(context):
    jd = draft(context)
    with repository.engine.begin() as conn:
        dbm.hr_review_events.drop(conn); dbm.hr_review_submissions.drop(conn)
        conn.execute(update(dbm.schema_version).values(version=12))
        conn.exec_driver_sql('PRAGMA user_version=12')
    repository.initialize(); repository.initialize()
    assert repository.get_hiring('job_descriptions', jd['id'], **identity(context)).model_dump(mode='json', by_alias=True) == jd
    with repository.engine.connect() as conn:
        assert conn.execute(select(dbm.schema_version.c.version)).scalar_one() == SCHEMA_VERSION == 14
        assert conn.exec_driver_sql('PRAGMA user_version').scalar_one() == 14
    assert submit(context, jd).status == 'pending_review'
