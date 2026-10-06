"""Phase 5 real API/storage acceptance; no model/provider calls."""
import pytest
from sqlalchemy import insert, select, update, delete
from sqlalchemy.exc import IntegrityError

from app.storage.database import repository, Repository, SCHEMA_VERSION
from app.storage import models as dbm
from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from app.models.schemas import HiringRequirementInput
from test_simulation_workspace_api import authenticated_context, cleanup, user_record

KINDS = ('requirements', 'role-knowledge', 'job-descriptions')

@pytest.fixture
def context():
    ctx = authenticated_context()
    ctx[0].headers['X-Workspace-Id'] = ctx[3]['id']
    repository.assign_organization_human_role(workspace_id=ctx[3]['id'], target_user_id=ctx[1]['id'],
        human_role='hr_recruiter', actor_user_id=ctx[1]['id'])
    try:
        yield ctx
    finally:
        cleanup(ctx)


def requirement(**changes):
    return dict(title='Platform engineer', purpose='Maintain internal services', requiredSkills=['Python'], **changes)


def create(client, kind='requirements', payload=None):
    response = client.post('/api/v1/hiring/' + kind, json=payload or requirement())
    assert response.status_code == 201, response.text
    return response.json()


def sources(client):
    req = create(client)
    knowledge = create(client, 'role-knowledge', {'title': 'Engineer', 'competencies': ['Reliability']})
    payload = {'title': 'Platform engineer', 'summary': 'Build internal services',
               'requirement': {'id': req['id'], 'revision': 1},
               'roleKnowledge': {'id': knowledge['id'], 'revision': 1}}
    return req, knowledge, payload


def test_persistent_sources_history_conflicts_and_reinitialization(context):
    client = context[0]
    req, knowledge, payload = sources(client)
    jd = create(client, 'job-descriptions', payload)
    for kind, record in zip(KINDS, (req, knowledge, jd)):
        path = '/api/v1/hiring/' + kind + '/' + record['id']
        changed = {**record['content'], 'title': 'Revised title', 'expectedRevision': 1}
        result = client.put(path, json=changed)
        assert result.status_code == 200, result.text
        assert result.json()['revision'] == 2
        assert client.put(path, json=changed).status_code == 409
        history = client.get(path + '/revisions').json()
        assert history[0] == record
        assert [v['revision'] for v in history] == [1, 2]
    repository.initialize()
    assert client.get('/api/v1/hiring/job-descriptions/' + jd['id']).json()['content']['requirement']['revision'] == 1
    assert client.get('/api/v1/hiring/requirements').json()[0]['revision'] == 2


@pytest.mark.parametrize('payload', [
    {'title': '', 'purpose': 'x'}, {'title': 'x', 'purpose': ' '},
    {'title': 'x', 'purpose': 'x', 'openings': 0}, {'title': 'x', 'purpose': 'x', 'openings': True},
    {'title': 'x', 'purpose': 'x', 'requiredSkills': [' ']},
    {'title': 'x', 'purpose': 'x', 'workspaceId': 'foreign'},
    {'title': 'x', 'purpose': 'x', 'status': 'approved'},
    {'title': 'x', 'purpose': 'x', 'responsibilities': ['x'] * 81},
    {'title': 'x' * 201, 'purpose': 'x'}])
def test_invalid_records_are_not_persisted(context, payload):
    assert context[0].post('/api/v1/hiring/requirements', json=payload).status_code == 422
    assert context[0].get('/api/v1/hiring/requirements').json() == []


@pytest.mark.parametrize('kind', KINDS)
def test_lifecycle_and_archive_read_only(context, kind):
    client = context[0]
    req, knowledge, payload = sources(client)
    record = {'requirements': req, 'role-knowledge': knowledge,
              'job-descriptions': create(client, 'job-descriptions', payload)}[kind]
    path = '/api/v1/hiring/' + kind + '/' + record['id']
    assert client.put(path, json={**record['content'], 'status': 'archived', 'expectedRevision': 1}).status_code == 200
    assert client.put(path, json={**record['content'], 'expectedRevision': 2}).status_code == 409
    assert client.get(path).json()['content']['status'] == 'archived'


def test_requirement_transitions_and_initial_state(context):
    client = context[0]
    req = create(client)
    path = '/api/v1/hiring/requirements/' + req['id']
    assert client.put(path, json={**req['content'], 'status': 'closed', 'expectedRevision': 1}).status_code == 409
    for revision, status in ((1, 'active'), (2, 'closed')):
        assert client.put(path, json={**req['content'], 'status': status, 'expectedRevision': revision}).status_code == 200
    assert client.put(path, json={**req['content'], 'status': 'active', 'expectedRevision': 3}).status_code == 409
    assert client.post('/api/v1/hiring/requirements', json={**requirement(), 'status': 'active'}).status_code == 409


def test_source_tenant_revision_and_archived_integrity(context):
    client, user, _, org, *_ = context
    req, knowledge, payload = sources(client)
    other, _ = repository.create_organization(creator_user_id=user['id'], name='Other')
    repository.assign_organization_human_role(workspace_id=other['id'], target_user_id=user['id'], human_role='hr_recruiter', actor_user_id=user['id'])
    assert client.post('/api/v1/hiring/job-descriptions', json=payload,
                       headers={'X-Workspace-Id': other['id']}).status_code == 404
    assert client.post('/api/v1/hiring/job-descriptions', json={**payload, 'requirement': {'id': req['id'], 'revision': 99}}).status_code == 404
    client.put('/api/v1/hiring/role-knowledge/' + knowledge['id'], json={**knowledge['content'], 'status': 'archived', 'expectedRevision': 1})
    assert client.post('/api/v1/hiring/job-descriptions', json=payload).status_code == 409
    assert client.post('/api/v1/hiring/job-descriptions', json={**payload, 'roleKnowledge': None}).status_code == 201
    # The database itself rejects a source from the wrong organization.
    with pytest.raises(IntegrityError):
        with repository.engine.begin() as connection:
            head, history = dbm.HR_TABLES['job_descriptions']
            connection.execute(insert(head).values(id='bad-jd', workspace_id=other['id'], revision=1,
                status='draft', created_by_user_id=user['id'], created_at=req['createdAt']))
            connection.execute(insert(history).values(record_id='bad-jd', workspace_id=other['id'], revision=1,
                updated_by_user_id=user['id'], updated_at=req['updatedAt'], payload=payload,
                requirement_id=req['id'], requirement_revision=1))


@pytest.mark.parametrize('iam', ['owner', 'admin', 'member'])
@pytest.mark.parametrize('hr,write', [(None, False), ('hr_recruiter', True), ('hr_reviewer', False), ('hr_approver', False)])
def test_iam_and_hr_permission_intersection(context, iam, hr, write):
    client, user, _, _, *_ = context
    repository.save_user(user_record('USR-founder'))
    org, code = repository.create_organization(creator_user_id='USR-founder', name='IAM matrix')
    if iam == 'owner':
        org, _ = repository.create_organization(creator_user_id=user['id'], name='Owned matrix')
    else:
        repository.join_organization(user_id=user['id'], join_code=code)
        if iam == 'admin':
            repository.change_organization_membership_role(workspace_id=org['id'], target_user_id=user['id'], actor_user_id='USR-founder', new_role='admin')
    actor = user['id'] if iam == 'owner' else 'USR-founder'
    if hr:
        repository.assign_organization_human_role(workspace_id=org['id'], target_user_id=user['id'], human_role=hr, actor_user_id=actor)
    client.headers['X-Workspace-Id'] = org['id']
    assert client.get('/api/v1/hiring/requirements').status_code == (200 if hr else 403)
    for kind, payload in [('requirements', requirement()), ('role-knowledge', {'title': 'Engineer'})]:
        assert client.post('/api/v1/hiring/' + kind, json=payload).status_code == (201 if write else 403)
    assert client.get('/api/v1/hiring/capabilities').json()['job_descriptions'] == write


def test_revocation_missing_context_personal_and_foreign_workspace(context):
    client, user, personal, org, *_ = context
    req = create(client)
    for kind in KINDS:
        assert client.get('/api/v1/hiring/' + kind, headers={'X-Workspace-Id': personal['id']}).status_code == 403
        assert client.get('/api/v1/hiring/' + kind, headers={'X-Workspace-Id': 'foreign'}).status_code == 404
    client.headers.pop('X-Workspace-Id')
    assert client.get('/api/v1/hiring/requirements').status_code == 403
    client.headers['X-Workspace-Id'] = org['id']
    repository.deactivate_organization_human_role(workspace_id=org['id'], target_user_id=user['id'], human_role='hr_recruiter', actor_user_id=user['id'])
    assert client.get('/api/v1/hiring/requirements/' + req['id']).status_code == 403
    with pytest.raises(AuthorizationError):
        repository.save_hiring('requirements', HiringRequirementInput(**requirement()), workspace_id=org['id'], user_id=user['id'])
    client.cookies.clear()
    assert client.get('/api/v1/hiring/requirements').status_code == 401


@pytest.mark.parametrize('kind', ['requirements', 'role_knowledge', 'job_descriptions'])
def test_immutable_sqlite_history(context, kind):
    client = context[0]
    _, _, payload = sources(client)
    create(client, 'job-descriptions', payload)
    _, history = dbm.HR_TABLES[kind]
    for mutation in (update(history).values(payload={}), delete(history)):
        with pytest.raises(IntegrityError):
            with repository.engine.begin() as connection:
                connection.execute(mutation)


def test_v11_migration_preserves_existing_data(tmp_path):
    repo = Repository('sqlite:///' + str(tmp_path / 'migration.db'))
    with repo.engine.begin() as connection:
        for table in dbm.metadata.sorted_tables:
            if not table.name.startswith('hr_'):
                table.create(connection)
        connection.execute(insert(dbm.schema_version).values(version=11, applied_at='before'))
        connection.exec_driver_sql('PRAGMA user_version=11')
    repo.save_user(user_record('USR-preserved'))
    original = repo.ensure_personal_workspace('USR-preserved')
    repo.initialize(); repo.initialize()
    assert repo.get_personal_workspace('USR-preserved')['id'] == original['id']
    with repo.engine.connect() as connection:
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == SCHEMA_VERSION
        assert connection.exec_driver_sql('PRAGMA user_version').scalar_one() == SCHEMA_VERSION


def test_api_member_revocation_denies_all_operations(context):
    client, user, _, org, *_ = context
    repository.save_user(user_record('USR-member'))
    other, code = repository.create_organization(creator_user_id='USR-member', name='Revocation')
    repository.join_organization(user_id=user['id'], join_code=code)
    repository.assign_organization_human_role(workspace_id=other['id'], target_user_id=user['id'], human_role='hr_recruiter', actor_user_id='USR-member')
    client.headers['X-Workspace-Id'] = other['id']
    req, knowledge, payload = sources(client)
    jd = create(client, 'job-descriptions', payload)
    repository.deactivate_organization_membership(workspace_id=other['id'], target_user_id=user['id'], actor_user_id='USR-member')
    for kind, record in zip(KINDS, (req, knowledge, jd)):
        path = '/api/v1/hiring/' + kind
        assert client.get(path).status_code == 404
        assert client.get(path + '/' + record['id']).status_code == 404
        assert client.get(path + '/' + record['id'] + '/revisions').status_code == 404
        assert client.post(path, json=record['content']).status_code == 404
        assert client.put(path + '/' + record['id'], json={**record['content'], 'expectedRevision': 1}).status_code == 404


def test_missing_repository_tenant_context_fails_closed(context):
    from app.security.tenant_db_context import TenantContextError
    with pytest.raises(TenantContextError):
        repository.list_hiring('requirements', workspace_id=None, user_id=context[1]['id'])
