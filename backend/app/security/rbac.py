"""Central role and permission semantics for workspace authorization.

Phase 4.3 starts by defining policy independently from member-management UI.
The database currently persists ``owner`` and ``member`` bootstrap roles; the
``admin`` role is defined here now and becomes persistable in the next RBAC
storage checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class WorkspaceRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Permission(str, Enum):
    WORKSPACE_VIEW = "workspace.view"
    SIMULATION_CREATE = "simulation.create"
    SIMULATION_VIEW = "simulation.view"
    SIMULATION_EVALUATE = "simulation.evaluate"
    SIMULATION_EXPORT = "simulation.export"

    ORGANIZATION_MEMBERS_VIEW = "organization.members.view"
    ORGANIZATION_MEMBERS_MANAGE = "organization.members.manage"
    ORGANIZATION_ADMINS_MANAGE = "organization.admins.manage"
    ORGANIZATION_SETTINGS_MANAGE = "organization.settings.manage"
    ORGANIZATION_OWNERSHIP_MANAGE = "organization.ownership.manage"


_BASE_WORKSPACE_PERMISSIONS = frozenset(
    {
        Permission.WORKSPACE_VIEW,
        Permission.SIMULATION_CREATE,
        Permission.SIMULATION_VIEW,
        Permission.SIMULATION_EVALUATE,
        Permission.SIMULATION_EXPORT,
    }
)

ROLE_PERMISSIONS: Mapping[WorkspaceRole, frozenset[Permission]] = {
    WorkspaceRole.MEMBER: _BASE_WORKSPACE_PERMISSIONS,
    WorkspaceRole.ADMIN: _BASE_WORKSPACE_PERMISSIONS
    | frozenset(
        {
            Permission.ORGANIZATION_MEMBERS_VIEW,
            Permission.ORGANIZATION_MEMBERS_MANAGE,
            Permission.ORGANIZATION_SETTINGS_MANAGE,
        }
    ),
    WorkspaceRole.OWNER: _BASE_WORKSPACE_PERMISSIONS
    | frozenset(
        {
            Permission.ORGANIZATION_MEMBERS_VIEW,
            Permission.ORGANIZATION_MEMBERS_MANAGE,
            Permission.ORGANIZATION_ADMINS_MANAGE,
            Permission.ORGANIZATION_SETTINGS_MANAGE,
            Permission.ORGANIZATION_OWNERSHIP_MANAGE,
        }
    ),
}

_ORGANIZATION_ONLY = frozenset(
    {
        Permission.ORGANIZATION_MEMBERS_VIEW,
        Permission.ORGANIZATION_MEMBERS_MANAGE,
        Permission.ORGANIZATION_ADMINS_MANAGE,
        Permission.ORGANIZATION_SETTINGS_MANAGE,
        Permission.ORGANIZATION_OWNERSHIP_MANAGE,
    }
)


class AuthorizationError(PermissionError):
    """Raised when an authenticated user lacks an RBAC permission."""


@dataclass(frozen=True)
class WorkspaceAuthorization:
    user_id: str
    workspace_id: str
    workspace_kind: str
    role: WorkspaceRole

    def allows(self, permission: Permission) -> bool:
        if (
            self.workspace_kind != "organization"
            and permission in _ORGANIZATION_ONLY
        ):
            return False

        return permission in ROLE_PERMISSIONS[self.role]

    def require(self, permission: Permission) -> None:
        if not self.allows(permission):
            raise AuthorizationError("Permission denied.")


class WorkspaceRepository(Protocol):
    def get_workspace(self, workspace_id: str): ...

    def get_organization_membership(
        self,
        workspace_id: str,
        user_id: str,
    ): ...


def _parse_role(value: str) -> WorkspaceRole:
    try:
        return WorkspaceRole(value)
    except (TypeError, ValueError) as exc:
        # Authorization must fail closed for unknown/corrupt role values.
        raise AuthorizationError("Permission denied.") from exc


def resolve_workspace_authorization(
    repository: WorkspaceRepository,
    *,
    user_id: str,
    workspace_id: str,
) -> WorkspaceAuthorization:
    """Resolve one user's effective RBAC role for an accessible workspace.

    Personal Workspaces have no membership row: their owning user receives the
    effective owner role for workspace actions, while organization-only
    permissions remain inapplicable. Organization access requires an active
    membership and a recognized role.
    """

    workspace = repository.get_workspace(workspace_id)

    if workspace is None or not workspace.get("active"):
        raise AuthorizationError("Permission denied.")

    if workspace.get("kind") == "personal":
        if workspace.get("personal_owner_user_id") != user_id:
            raise AuthorizationError("Permission denied.")

        return WorkspaceAuthorization(
            user_id=user_id,
            workspace_id=workspace_id,
            workspace_kind="personal",
            role=WorkspaceRole.OWNER,
        )

    if workspace.get("kind") != "organization":
        raise AuthorizationError("Permission denied.")

    membership = repository.get_organization_membership(
        workspace_id,
        user_id,
    )

    if membership is None or not membership.get("active"):
        raise AuthorizationError("Permission denied.")

    return WorkspaceAuthorization(
        user_id=user_id,
        workspace_id=workspace_id,
        workspace_kind="organization",
        role=_parse_role(membership.get("membership_role")),
    )
