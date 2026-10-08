"""The same one-time invitation policy under isolated non-bypass FORCE RLS."""
import pytest
from sqlalchemy import update

from app.storage import models as dbm
from test_postgres_data_plane_integration import pg_repo
from test_tenant_repository_primitives import make_user
from test_product_invites import (
    test_invites_generate_consume_revoke_replace_no_plaintext,
    test_member_and_cross_tenant_management_denied,
    test_admin_can_manage_invites_but_removed_admin_cannot,
    test_concurrent_consumption_has_exactly_one_winner,
    test_concurrent_self_changes_cannot_remove_both_owners,
)


@pytest.fixture
def repo(pg_repo):
    for uid in ('owner', 'admin', 'member', 'outsider'):
        pg_repo.save_user(make_user(uid))
        pg_repo.ensure_personal_workspace(uid)
    return pg_repo


def test_v13_additive_postgres_invite_migration(repo):
    org, code = repo.create_organization(creator_user_id='owner', name='Legacy PostgreSQL invite')
    with repo.engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE workspaces DROP COLUMN invite_history')
        connection.execute(update(dbm.schema_version).values(version=13))
    repo.initialize(); repo.initialize()
    assert repo.manage_organization_invites(workspace_id=org['id'], user_id='owner')[0]['id'] == 'legacy'
    repo.join_organization(user_id='member', join_code=code)
    assert repo.manage_organization_invites(workspace_id=org['id'], user_id='owner')[0]['status'] == 'consumed'

from test_product_invites import test_nonactive_history_with_stale_digest_fails_closed
from test_product_invites import test_disabled_identity_does_not_count_as_an_active_owner
