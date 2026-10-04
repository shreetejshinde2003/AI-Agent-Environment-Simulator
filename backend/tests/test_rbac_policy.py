from datetime import datetime, timezone

import pytest

from app.security.rbac import (
    AuthorizationError,
    Permission,
    ROLE_PERMISSIONS,
    WorkspaceRole,
    resolve_workspace_authorization,
)
from app.storage.database import Repository


def _now():
    return datetime.now(timezone.utc).isoformat()


def _user(user_id: str):
    return {
        "id": user_id,
        "google_sub": f"google-{user_id}",
        "email": f"{user_id}@example.test",
        "display_name": user_id.title(),
        "profile_picture": None,
        "email_verified": True,
        "active": True,
        "created_at": _now(),
        "last_login_at": _now(),
    }


def test_role_permission_matrix_is_explicit_and_least_privilege():
    member = ROLE_PERMISSIONS[WorkspaceRole.MEMBER]
    admin = ROLE_PERMISSIONS[WorkspaceRole.ADMIN]
    owner = ROLE_PERMISSIONS[WorkspaceRole.OWNER]

    assert Permission.SIMULATION_CREATE in member
    assert Permission.SIMULATION_EXPORT in member
    assert Permission.ORGANIZATION_MEMBERS_VIEW not in member

    assert Permission.ORGANIZATION_MEMBERS_MANAGE in admin
    assert Permission.ORGANIZATION_SETTINGS_MANAGE in admin
    assert Permission.ORGANIZATION_ADMINS_MANAGE not in admin
    assert Permission.ORGANIZATION_OWNERSHIP_MANAGE not in admin

    assert Permission.ORGANIZATION_ADMINS_MANAGE in owner
    assert Permission.ORGANIZATION_OWNERSHIP_MANAGE in owner
    assert member < admin < owner


def test_personal_workspace_owner_can_use_workspace_but_not_org_admin_actions(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'rbac-personal.db'}")
    repo.initialize()
    repo.save_user(_user("alice"))
    personal = repo.ensure_personal_workspace("alice")

    authz = resolve_workspace_authorization(
        repo,
        user_id="alice",
        workspace_id=personal["id"],
    )

    assert authz.role is WorkspaceRole.OWNER
    assert authz.allows(Permission.WORKSPACE_VIEW)
    assert authz.allows(Permission.SIMULATION_CREATE)
    assert not authz.allows(Permission.ORGANIZATION_MEMBERS_MANAGE)

    with pytest.raises(AuthorizationError):
        authz.require(Permission.ORGANIZATION_SETTINGS_MANAGE)


def test_organization_owner_receives_owner_permissions(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'rbac-owner.db'}")
    repo.initialize()
    repo.save_user(_user("alice"))
    workspace, _ = repo.create_organization(
        creator_user_id="alice",
        name="IICT",
    )

    authz = resolve_workspace_authorization(
        repo,
        user_id="alice",
        workspace_id=workspace["id"],
    )

    assert authz.role is WorkspaceRole.OWNER
    assert authz.allows(Permission.ORGANIZATION_MEMBERS_MANAGE)
    assert authz.allows(Permission.ORGANIZATION_ADMINS_MANAGE)
    assert authz.allows(Permission.ORGANIZATION_OWNERSHIP_MANAGE)


def test_organization_member_receives_member_permissions_only(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'rbac-member.db'}")
    repo.initialize()
    repo.save_user(_user("alice"))
    repo.save_user(_user("bob"))
    workspace, join_code = repo.create_organization(
        creator_user_id="alice",
        name="IICT",
    )
    repo.join_organization(user_id="bob", join_code=join_code)

    authz = resolve_workspace_authorization(
        repo,
        user_id="bob",
        workspace_id=workspace["id"],
    )

    assert authz.role is WorkspaceRole.MEMBER
    assert authz.allows(Permission.SIMULATION_VIEW)
    assert not authz.allows(Permission.ORGANIZATION_MEMBERS_VIEW)
    assert not authz.allows(Permission.ORGANIZATION_SETTINGS_MANAGE)


def test_inactive_or_unrelated_membership_fails_closed(tmp_path):
    repo = Repository(f"sqlite:///{tmp_path / 'rbac-deny.db'}")
    repo.initialize()
    repo.save_user(_user("alice"))
    repo.save_user(_user("bob"))
    workspace, join_code = repo.create_organization(
        creator_user_id="alice",
        name="IICT",
    )

    with pytest.raises(AuthorizationError):
        resolve_workspace_authorization(
            repo,
            user_id="bob",
            workspace_id=workspace["id"],
        )

    repo.join_organization(user_id="bob", join_code=join_code)
    membership = repo.get_organization_membership(workspace["id"], "bob")
    membership["active"] = False
    repo.save_organization_membership(membership)

    with pytest.raises(AuthorizationError):
        resolve_workspace_authorization(
            repo,
            user_id="bob",
            workspace_id=workspace["id"],
        )


def test_unknown_membership_role_fails_closed():
    class FakeRepository:
        def get_workspace(self, workspace_id):
            return {
                "id": workspace_id,
                "kind": "organization",
                "active": True,
            }

        def get_organization_membership(self, workspace_id, user_id):
            return {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "membership_role": "superuser",
                "active": True,
            }

    with pytest.raises(AuthorizationError):
        resolve_workspace_authorization(
            FakeRepository(),
            user_id="alice",
            workspace_id="WS-test",
        )
