"""Phase 7 real PostgreSQL FORCE RLS, immutable events and tenant transactions."""
import pytest
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import insert, select, text, update, delete
from sqlalchemy.exc import DBAPIError
from app.models.schemas import HRReviewSubmissionInput, HRReviewDecisionInput
from app.storage import models as dbm
from app.storage.hiring import HiringError
from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from test_postgres_data_plane_integration import pg_repo
from test_hiring_postgres import setup, records

TABLES = (dbm.hr_review_submissions, dbm.hr_review_events)


def prepare(repo):
    owner, member = setup(repo)
    jd = records(repo, owner)[2]
    for role in ('hr_reviewer', 'hr_approver'):
        repo.assign_organization_human_role(workspace_id=owner['workspace_id'], target_user_id=owner['user_id'],
            human_role=role, actor_user_id=owner['user_id'])
    submission = repo.submit_review(HRReviewSubmissionInput(job_description={'id': jd.id, 'revision': 1}), **owner)
    return owner, member, submission


def decision(version, action):
    return HRReviewDecisionInput(expected_version=version, decision=action, notes='Actual authenticated human decision')


def test_pg_force_rls_immutable_audit_and_actor_integrity(pg_repo):
    owner, member, record = prepare(pg_repo)
    for table in TABLES:
        with pg_repo.engine.connect() as conn:
            assert conn.execute(select(table)).all() == []
            assert tuple(conn.execute(text('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:name)'), {'name': table.name}).one()) == (True, True)
        with tenant_transaction(pg_repo.engine, **member) as conn:
            assert conn.execute(select(table)).all()
            assert conn.execute(update(table).values(id='rewrite')).rowcount == 0
            assert conn.execute(delete(table)).rowcount == 0
    reviewed = pg_repo.decide_review(record.id, decision(1, 'recommend'), **owner)
    approved = pg_repo.decide_review(record.id, decision(2, 'approve'), approval=True, **owner)
    assert approved.status == 'approved'
    assert approved.history[:2] == reviewed.history
    pg_repo.initialize()
    assert pg_repo.get_review(record.id, **owner) == approved
    with pytest.raises(DBAPIError):
        with tenant_transaction(pg_repo.engine, **owner) as conn:
            conn.execute(insert(dbm.hr_review_events).values(id='forged', workspace_id=owner['workspace_id'],
                submission_id=record.id, version=4, actor_user_id=member['user_id'], occurred_at='now',
                action='approve', from_status='reviewed', to_status='approved', notes='Forged actor'))


def test_pg_cross_tenant_and_personal_workspaces(pg_repo):
    owner, member, record = prepare(pg_repo)
    other, _ = pg_repo.create_organization(creator_user_id=member['user_id'], name='Foreign HR')
    outsider = dict(workspace_id=other['id'], user_id=member['user_id'])
    pg_repo.assign_organization_human_role(workspace_id=other['id'], target_user_id=member['user_id'],
        human_role='hr_approver', actor_user_id=member['user_id'])
    assert pg_repo.list_reviews(**outsider) == []
    with pytest.raises(HiringError): pg_repo.get_review(record.id, **outsider)
    with tenant_transaction(pg_repo.engine, **outsider) as conn:
        for table in TABLES: assert conn.execute(select(table)).all() == []
    personal = dict(workspace_id=pg_repo.get_personal_workspace(member['user_id'])['id'], user_id=member['user_id'])
    with pytest.raises(AuthorizationError): pg_repo.list_reviews(**personal)


@pytest.mark.parametrize('revoke', ['membership', 'role', 'user', 'workspace'])
def test_pg_revocation_fails_closed(pg_repo, revoke):
    owner, member, record = prepare(pg_repo)
    pg_repo.assign_organization_human_role(workspace_id=owner['workspace_id'], target_user_id=member['user_id'],
        human_role='hr_reviewer', actor_user_id=owner['user_id'])
    if revoke == 'membership':
        pg_repo.deactivate_organization_membership(workspace_id=owner['workspace_id'], target_user_id=member['user_id'], actor_user_id=owner['user_id'])
    elif revoke == 'role':
        for role in ('hr_recruiter', 'hr_reviewer'):
            pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'], target_user_id=member['user_id'], human_role=role, actor_user_id=owner['user_id'])
    else:
        with tenant_transaction(pg_repo.engine, **owner) as conn:
            table = dbm.users if revoke == 'user' else dbm.workspaces
            key = member['user_id'] if revoke == 'user' else owner['workspace_id']
            conn.execute(update(table).where(table.c.id == key).values(active=False))
    with pytest.raises(AuthorizationError): pg_repo.decide_review(record.id, decision(1, 'recommend'), **member)
    with tenant_transaction(pg_repo.engine, **member) as conn:
        for table in TABLES: assert conn.execute(select(table)).all() == []


def test_pg_v12_migration_preserves_jd_and_old_approval(pg_repo):
    owner, _, record = prepare(pg_repo)
    reviewed = pg_repo.decide_review(record.id, decision(1, 'recommend'), **owner)
    with pg_repo.engine.begin() as conn: conn.execute(update(dbm.schema_version).values(version=12))
    pg_repo.initialize(); pg_repo.initialize()
    assert pg_repo.get_review(record.id, **owner) == reviewed
    pg_repo.decide_review(record.id, decision(2, 'approve'), approval=True, **owner)
    changed = pg_repo.save_hiring('job_descriptions', record.job_description.content.model_copy(update={'summary': 'Human revised'}),
        record_id=record.job_description.id, expected_revision=1, **owner)
    newer = pg_repo.submit_review(HRReviewSubmissionInput(job_description={'id': changed.id, 'revision': 2}), **owner)
    assert newer.status == 'pending_review'
    assert pg_repo.get_review(record.id, **owner).status == 'approved'
    assert pg_repo.get_review(record.id, **owner).stale


def test_pg_additive_v12_without_review_tables(pg_repo):
    owner, _ = setup(pg_repo)
    jd = records(pg_repo, owner)[2]
    with pg_repo.engine.begin() as conn:
        dbm.hr_review_events.drop(conn); dbm.hr_review_submissions.drop(conn)
        conn.execute(update(dbm.schema_version).values(version=12))
    pg_repo.initialize()
    assert pg_repo.get_hiring('job_descriptions', jd.id, **owner) == jd
    assert pg_repo.submit_review(HRReviewSubmissionInput(job_description={'id': jd.id, 'revision': 1}), **owner).status == 'pending_review'


def test_pg_concurrent_decisions_and_jd_edit_conflict(pg_repo):
    owner, _, record = prepare(pg_repo)
    # Use two real connections in this one bounded concurrency test.
    from sqlalchemy import create_engine
    old = pg_repo._engine
    with old.connect() as conn: search_path = conn.exec_driver_sql('SHOW search_path').scalar_one()
    pg_repo._engine = create_engine(old.url, pool_size=2, max_overflow=0,
        connect_args={'options': '-csearch_path=' + search_path})
    def attempt(_):
        try: return pg_repo.decide_review(record.id, decision(1, 'recommend'), **owner).status
        except HiringError as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(attempt, range(2)))
    assert set(results) == {'reviewed', 409}
    pg_repo._engine.dispose(); pg_repo._engine = old
    pg_repo.save_hiring('job_descriptions', record.job_description.content.model_copy(update={'summary': 'Changed'}),
        record_id=record.job_description.id, expected_revision=1, **owner)
    with pytest.raises(HiringError): pg_repo.decide_review(record.id, decision(2, 'approve'), approval=True, **owner)


def test_pg_recruiter_cannot_insert_review_or_approval_via_sql(pg_repo):
    owner, member, record = prepare(pg_repo)
    for action, version, before, after in [('recommend', 2, 'pending_review', 'reviewed'), ('approve', 3, 'reviewed', 'approved')]:
        with pytest.raises(DBAPIError):
            with tenant_transaction(pg_repo.engine, **member) as conn:
                conn.execute(insert(dbm.hr_review_events).values(id='fake-'+action, workspace_id=owner['workspace_id'],
                    submission_id=record.id, version=version, actor_user_id=member['user_id'], occurred_at='now',
                    action=action, from_status=before, to_status=after, notes='Not authorized'))
    assert pg_repo.get_review(record.id, **owner).version == 1
