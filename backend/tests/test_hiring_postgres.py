"""Restricted local PostgreSQL acceptance, isolated schemas and real FORCE RLS."""
import pytest
from sqlalchemy import insert, select, text, update, delete
from sqlalchemy.exc import DBAPIError

from app.models.schemas import HiringRequirementInput, RoleKnowledgeInput, JobDescriptionInput
from app.storage import models as dbm
from app.storage.database import SCHEMA_VERSION
from app.storage.hiring import HiringError
from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from test_postgres_data_plane_integration import pg_repo


def setup(repo):
    org, code = repo.create_organization(creator_user_id='USR-a', name='Hiring organization')
    repo.join_organization(user_id='USR-b', join_code=code)
    for user in ('USR-a', 'USR-b'):
        repo.assign_organization_human_role(workspace_id=org['id'], target_user_id=user,
            human_role='hr_recruiter', actor_user_id='USR-a')
    return dict(workspace_id=org['id'], user_id='USR-a'), dict(workspace_id=org['id'], user_id='USR-b')


def records(repo, scope):
    req = repo.save_hiring('requirements', HiringRequirementInput(title='Engineer', purpose='Internal services'), **scope)
    knowledge = repo.save_hiring('role_knowledge', RoleKnowledgeInput(title='Engineer'), **scope)
    jd = repo.save_hiring('job_descriptions', JobDescriptionInput(title='Engineer', summary='Build services',
        requirement={'id': req.id, 'revision': 1}, role_knowledge={'id': knowledge.id, 'revision': 1}), **scope)
    return req, knowledge, jd


def test_force_rls_source_revision_history_and_migration(pg_repo):
    owner, _ = setup(pg_repo)
    saved = records(pg_repo, owner)
    for kind, record in zip(dbm.HR_TABLES, saved):
        changed = pg_repo.save_hiring(kind, record.content.model_copy(update={'title': 'Updated'}),
            record_id=record.id, expected_revision=1, **owner)
        assert changed.revision == 2
        assert pg_repo.get_hiring(kind, record.id, revisions=True, **owner)[0] == record
        for table in dbm.HR_TABLES[kind]:
            with pg_repo.engine.connect() as connection:
                assert connection.execute(select(table)).all() == []
                state = connection.execute(text('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=to_regclass(:name)'), {'name': table.name}).one()
                assert tuple(state) == (True, True)
        _, history = dbm.HR_TABLES[kind]
        with tenant_transaction(pg_repo.engine, **owner) as connection:
            assert connection.execute(update(history).values(payload={})).rowcount == 0
            assert connection.execute(delete(history)).rowcount == 0
    # Operational V11 -> V12 activation repeatability preserves all records.
    with pg_repo.engine.begin() as connection:
        connection.execute(update(dbm.schema_version).values(version=11))
    pg_repo.initialize(); pg_repo.initialize()
    assert pg_repo.get_hiring('job_descriptions', saved[2].id, **owner).content.requirement.revision == 1
    with pg_repo.engine.connect() as connection:
        assert connection.execute(select(dbm.schema_version.c.version)).scalar_one() == SCHEMA_VERSION


def test_cross_tenant_reads_writes_sources_and_missing_context(pg_repo):
    owner, _ = setup(pg_repo)
    req, knowledge, jd = records(pg_repo, owner)
    other, _ = pg_repo.create_organization(creator_user_id='USR-b', name='Other organization')
    outsider = dict(workspace_id=other['id'], user_id='USR-b')
    pg_repo.assign_organization_human_role(workspace_id=other['id'], target_user_id='USR-b', human_role='hr_recruiter', actor_user_id='USR-b')
    for kind, record in zip(dbm.HR_TABLES, (req, knowledge, jd)):
        assert pg_repo.list_hiring(kind, **outsider) == []
        with pytest.raises(HiringError) as absent:
            pg_repo.get_hiring(kind, record.id, **outsider)
        assert absent.value.status_code == 404
        for table in dbm.HR_TABLES[kind]:
            with tenant_transaction(pg_repo.engine, **outsider) as connection:
                assert connection.execute(select(table)).all() == []
                assert connection.execute(delete(table)).rowcount == 0
        head, _ = dbm.HR_TABLES[kind]
        with pytest.raises(DBAPIError):
            with tenant_transaction(pg_repo.engine, **owner) as connection:
                connection.execute(update(head).values(workspace_id=other['id']))
    with pytest.raises(HiringError):
        pg_repo.save_hiring('job_descriptions', jd.content, **outsider)
    for identity in ({}, {'workspace_id': owner['workspace_id'], 'user_id': 'USR-b'}):
        # USR-b is a member here; remove its HR role before spoofing context.
        if identity:
            pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'], target_user_id='USR-b', human_role='hr_recruiter', actor_user_id='USR-a')
        with pg_repo.engine.begin() as connection:
            if identity:
                connection.execute(text("SELECT set_config('app.current_workspace_id', :ws, true), set_config('app.current_user_id', :u, true)"), {'ws': identity['workspace_id'], 'u': identity['user_id']})
            assert connection.execute(select(dbm.HR_TABLES['requirements'][0])).all() == []
            with pytest.raises(DBAPIError):
                connection.execute(insert(dbm.HR_TABLES['requirements'][0]).values(id='spoofed', workspace_id=owner['workspace_id'],
                    revision=1, status='draft', created_by_user_id='USR-b', created_at=req.created_at.isoformat()))


@pytest.mark.parametrize('revoke', ['membership', 'hr_role', 'user', 'workspace'])
def test_revocation_invalidates_repository_and_rls(pg_repo, revoke):
    owner, member = setup(pg_repo)
    req, _, _ = records(pg_repo, owner)
    assert pg_repo.get_hiring('requirements', req.id, **member).id == req.id
    if revoke == 'membership':
        pg_repo.deactivate_organization_membership(workspace_id=owner['workspace_id'], target_user_id='USR-b', actor_user_id='USR-a')
    elif revoke == 'hr_role':
        pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'], target_user_id='USR-b', human_role='hr_recruiter', actor_user_id='USR-a')
    else:
        with tenant_transaction(pg_repo.engine, **owner) as connection:
            table = dbm.users if revoke == 'user' else dbm.workspaces
            key = 'USR-b' if revoke == 'user' else owner['workspace_id']
            connection.execute(update(table).where(table.c.id == key).values(active=False))
    with pytest.raises(AuthorizationError):
        pg_repo.list_hiring('requirements', **member)
    with tenant_transaction(pg_repo.engine, **member) as connection:
        for head, history in dbm.HR_TABLES.values():
            assert connection.execute(select(head)).all() == []
            assert connection.execute(select(history)).all() == []


@pytest.mark.parametrize('human_role', ['hr_reviewer', 'hr_approver'])
def test_read_only_human_roles_have_no_draft_authority(pg_repo, human_role):
    owner, member = setup(pg_repo)
    req, _, _ = records(pg_repo, owner)
    pg_repo.deactivate_organization_human_role(workspace_id=owner['workspace_id'], target_user_id='USR-b', human_role='hr_recruiter', actor_user_id='USR-a')
    pg_repo.assign_organization_human_role(workspace_id=owner['workspace_id'], target_user_id='USR-b', human_role=human_role, actor_user_id='USR-a')
    assert pg_repo.get_hiring('requirements', req.id, **member).id == req.id
    with pytest.raises(AuthorizationError):
        pg_repo.save_hiring('requirements', req.content, **member)
    with tenant_transaction(pg_repo.engine, **member) as connection:
        assert connection.execute(update(dbm.HR_TABLES['requirements'][0]).values(status='closed')).rowcount == 0


def test_additive_postgres_v11_without_hr_tables_preserves_identity(pg_repo):
    personal = pg_repo.get_personal_workspace('USR-a')
    with pg_repo.engine.begin() as connection:
        for table in reversed(dbm.metadata.sorted_tables):
            if table.name.startswith('hr_'):
                table.drop(connection)
        connection.execute(update(dbm.schema_version).values(version=11))
    pg_repo.initialize(); pg_repo.initialize()
    assert pg_repo.get_personal_workspace('USR-a')['id'] == personal['id']
    with pg_repo.engine.connect() as connection:
        for head, history in dbm.HR_TABLES.values():
            assert connection.execute(select(head)).all() == []
            assert connection.execute(select(history)).all() == []
    owner, _ = setup(pg_repo)
    assert len(records(pg_repo, owner)) == 3
