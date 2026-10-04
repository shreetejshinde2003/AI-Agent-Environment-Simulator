"""HR-domain human roles and capabilities.

These roles are intentionally separate from workspace IAM roles such as
owner/admin/member and from AI-agent identities. A person may hold more than
one HR-domain role inside the same Organization workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class HRHumanRole(str, Enum):
    RECRUITER = "hr_recruiter"
    REVIEWER = "hr_reviewer"
    APPROVER = "hr_approver"


class HRHumanPermission(str, Enum):
    HIRING_REQUEST_VIEW = "hr.hiring_request.view"
    HIRING_REQUEST_MANAGE = "hr.hiring_request.manage"
    JD_DRAFT_EDIT = "hr.jd.draft.edit"
    JD_REVIEW = "hr.jd.review"
    JD_REQUEST_REVISION = "hr.jd.request_revision"
    JD_APPROVE = "hr.jd.approve"
    JD_REJECT = "hr.jd.reject"


ROLE_PERMISSIONS: Mapping[HRHumanRole, frozenset[HRHumanPermission]] = {
    HRHumanRole.RECRUITER: frozenset(
        {
            HRHumanPermission.HIRING_REQUEST_VIEW,
            HRHumanPermission.HIRING_REQUEST_MANAGE,
            HRHumanPermission.JD_DRAFT_EDIT,
        }
    ),
    HRHumanRole.REVIEWER: frozenset(
        {
            HRHumanPermission.HIRING_REQUEST_VIEW,
            HRHumanPermission.JD_REVIEW,
            HRHumanPermission.JD_REQUEST_REVISION,
        }
    ),
    HRHumanRole.APPROVER: frozenset(
        {
            HRHumanPermission.HIRING_REQUEST_VIEW,
            HRHumanPermission.JD_REVIEW,
            HRHumanPermission.JD_APPROVE,
            HRHumanPermission.JD_REJECT,
        }
    ),
}


@dataclass(frozen=True)
class HRHumanAuthorization:
    user_id: str
    workspace_id: str
    roles: frozenset[HRHumanRole]

    def allows(self, permission: HRHumanPermission) -> bool:
        return any(
            permission in ROLE_PERMISSIONS[role]
            for role in self.roles
        )


class HRRoleRepository(Protocol):
    def get_workspace(self, workspace_id: str): ...

    def get_organization_membership(self, workspace_id: str, user_id: str): ...

    def list_organization_human_roles(
        self,
        workspace_id: str,
        *,
        user_id: str | None = None,
        active_only: bool = True,
    ): ...


def resolve_hr_human_authorization(
    repository: HRRoleRepository,
    *,
    user_id: str,
    workspace_id: str,
) -> HRHumanAuthorization:
    """Resolve active HR-domain roles for one active organization member.

    Personal Workspaces never receive HR-domain role assignments. Unknown or
    corrupt role values fail closed by being ignored rather than granting any
    capability.
    """

    workspace = repository.get_workspace(workspace_id)
    if (
        workspace is None
        or workspace.get("kind") != "organization"
        or not workspace.get("active")
    ):
        return HRHumanAuthorization(user_id, workspace_id, frozenset())

    membership = repository.get_organization_membership(workspace_id, user_id)
    if membership is None or not membership.get("active"):
        return HRHumanAuthorization(user_id, workspace_id, frozenset())

    roles: set[HRHumanRole] = set()
    for assignment in repository.list_organization_human_roles(
        workspace_id,
        user_id=user_id,
        active_only=True,
    ):
        try:
            roles.add(HRHumanRole(assignment.get("human_role")))
        except (TypeError, ValueError):
            continue

    return HRHumanAuthorization(
        user_id=user_id,
        workspace_id=workspace_id,
        roles=frozenset(roles),
    )
