"""Owner/admin managed, hashed one-time invitations and additive V14 migration."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select, update

from app.security.rbac import AuthorizationError
from app.security.tenant_db_context import tenant_transaction
from app.storage import models as dbm
from app.storage.database import Repository
from test_tenant_repository_primitives import make_user


@pytest.fixture
def repo(tmp_path):
    result = Repository(f"sqlite:///{tmp_path / 'invites.db'}")
    result.initialize()
    for uid in ('owner', 'admin', 'member', 'outsider'):
        result.save_user(make_user(uid))
        result.ensure_personal_workspace(uid)
    yield result
    result.engine.dispose()


def test_invites_generate_consume_revoke_replace_no_plaintext(repo):
    org, initial = repo.create_organization(creator_user_id='owner', name='Invitations')
    scope = dict(workspace_id=org['id'], user_id='owner')
    generated = repo.manage_organization_invites(**scope, action='generate')
    with pytest.raises(LookupError):
        repo.join_organization(user_id='member', join_code=initial)
    code = generated['joinCode']
    repo.join_organization(user_id='member', join_code=code)
    with pytest.raises(LookupError):
        repo.join_organization(user_id='outsider', join_code=code)
    history = repo.manage_organization_invites(**scope)
    assert [i['status'] for i in history] == ['revoked', 'consumed']
    assert history[-1]['usedByUserId'] == 'member' and history[-1]['usedAt']
    revoked = repo.manage_organization_invites(**scope, action='generate')
    repo.manage_organization_invites(**scope, action='revoke', invite_id=revoked['invites'][-1]['id'])
    with pytest.raises(LookupError):
        repo.join_organization(user_id='outsider', join_code=revoked['joinCode'])
    with tenant_transaction(repo.engine, workspace_id=org["id"], user_id="owner") as connection:
        stored = str(dict(connection.execute(select(dbm.workspaces).where(dbm.workspaces.c.id == org['id'])).mappings().one()))
        assert code not in stored and revoked['joinCode'] not in stored
    replacement = repo.manage_organization_invites(**scope, action='generate')
    assert repo.join_organization(user_id='outsider', join_code=replacement['joinCode'])[1]['active']


@pytest.mark.parametrize('action', ['list', 'generate', 'revoke'])
def test_member_and_cross_tenant_management_denied(repo, action):
    org, code = repo.create_organization(creator_user_id='owner', name='Private')
    repo.join_organization(user_id='member', join_code=code)
    for uid in ('member', 'outsider'):
        with pytest.raises(AuthorizationError):
            repo.manage_organization_invites(workspace_id=org['id'], user_id=uid, action=action)


def test_admin_can_manage_invites_but_removed_admin_cannot(repo):
    org, code = repo.create_organization(creator_user_id='owner', name='Admin managed')
    repo.join_organization(user_id='admin', join_code=code)
    repo.change_organization_membership_role(workspace_id=org['id'], actor_user_id='owner', target_user_id='admin', new_role='admin')
    assert repo.manage_organization_invites(workspace_id=org['id'], user_id='admin', action='generate')['joinCode']
    repo.deactivate_organization_membership(workspace_id=org['id'], actor_user_id='owner', target_user_id='admin')
    with pytest.raises(AuthorizationError):
        repo.manage_organization_invites(workspace_id=org['id'], user_id='admin', action='generate')


def test_concurrent_consumption_has_exactly_one_winner(repo):
    org, code = repo.create_organization(creator_user_id='owner', name='Concurrent invite')
    def join(uid):
        try:
            repo.join_organization(user_id=uid, join_code=code)
            return 'consumed'
        except LookupError:
            return 'unavailable'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(join, ['member', 'outsider'])) == ['consumed', 'unavailable']
    assert len([i for i in repo.manage_organization_invites(workspace_id=org['id'], user_id='owner') if i['status'] == 'consumed']) == 1


def test_v13_migration_preserves_legacy_code_and_records_consumption(repo):
    org, code = repo.create_organization(creator_user_id='owner', name='Legacy invite')
    with repo.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE workspaces DROP COLUMN invite_history')
        connection.execute(update(dbm.schema_version).values(version=13))
        connection.exec_driver_sql('PRAGMA user_version=13')
    repo.initialize(); repo.initialize()
    assert repo.manage_organization_invites(workspace_id=org['id'], user_id='owner')[0]['id'] == 'legacy'
    repo.join_organization(user_id='member', join_code=code)
    assert repo.manage_organization_invites(workspace_id=org['id'], user_id='owner')[0]['status'] == 'consumed'


@pytest.mark.parametrize('action', ['demote', 'remove'])
def test_concurrent_self_changes_cannot_remove_both_owners(repo, action):
    org, code = repo.create_organization(creator_user_id='owner', name='Owner concurrency')
    repo.join_organization(user_id='admin', join_code=code)
    scope = dict(workspace_id=org['id'])
    repo.change_organization_membership_role(**scope, actor_user_id='owner', target_user_id='admin', new_role='owner')
    def change(uid):
        try:
            if action == 'demote':
                repo.change_organization_membership_role(**scope, actor_user_id=uid, target_user_id=uid, new_role='member')
            else:
                repo.deactivate_organization_membership(**scope, actor_user_id=uid, target_user_id=uid)
            return 'changed'
        except (ValueError, AuthorizationError):
            return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, ['owner', 'admin'])) == ['blocked', 'changed']
    with tenant_transaction(repo.engine, workspace_id=org["id"], user_id="owner" if (repo.get_organization_membership(org["id"], "owner") or {}).get("active") else "admin") as connection:
        assert len(connection.execute(select(dbm.organization_memberships).where(
            dbm.organization_memberships.c.workspace_id == org['id'],
            dbm.organization_memberships.c.membership_role == 'owner',
            dbm.organization_memberships.c.active.is_(True))).all()) == 1


def test_nonactive_history_with_stale_digest_fails_closed(repo):
    org, code = repo.create_organization(creator_user_id='owner', name='History integrity')
    with tenant_transaction(repo.engine, workspace_id=org['id'], user_id='owner') as connection:
        history = [dict(item, status='revoked') for item in org['invite_history']]
        connection.execute(update(dbm.workspaces).where(dbm.workspaces.c.id == org['id']).values(invite_history=history))
    with pytest.raises(LookupError):
        repo.join_organization(user_id='member', join_code=code)


@pytest.mark.parametrize('action', ['demote', 'remove'])
def test_disabled_identity_does_not_count_as_an_active_owner(repo, action):
    org, code = repo.create_organization(creator_user_id='owner', name='Active owner guard')
    repo.join_organization(user_id='admin', join_code=code)
    scope = dict(workspace_id=org['id'], actor_user_id='owner')
    repo.change_organization_membership_role(**scope, target_user_id='admin', new_role='owner')
    disabled = make_user('admin'); disabled['active'] = False
    repo.save_user(disabled)
    with pytest.raises(ValueError, match='last active organization owner'):
        if action == 'demote':
            repo.change_organization_membership_role(**scope, target_user_id='owner', new_role='member')
        else:
            repo.deactivate_organization_membership(**scope, target_user_id='owner')
