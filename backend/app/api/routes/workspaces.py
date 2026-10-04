"""Organization workspace endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.api.routes import auth
from app.models.schemas import (
    CreateOrganizationRequest,
    JoinOrganizationRequest,
    ChangeOrganizationMemberRoleRequest,
    OrganizationCreated,
    OrganizationJoined,
    OrganizationMemberListResponse,
    OrganizationMemberRoleChanged,
    OrganizationMemberSummary,
    WorkspaceListResponse,
    WorkspaceSummary,
    AssignOrganizationHumanRoleRequest,
    OrganizationHumanRoleAssignment,
    OrganizationHumanRoleChanged,
    OrganizationHumanRoleListResponse,
)
from app.security.rbac import (
    AuthorizationError,
    Permission,
    resolve_workspace_authorization,
)
from app.storage.database import repository


router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
)


def require_request_permission(
    request: Request,
    workspace_id: str | None,
    permission: Permission,
):
    """Resolve one workspace and enforce its RBAC permission consistently.

    Tenant existence remains hidden behind 404. An authenticated user who can
    access the workspace but lacks the requested action receives 403.
    """

    user, _ = auth._authenticated_record(request)
    request.state.authenticated_user_id = user["id"]

    try:
        workspace = repository.resolve_workspace_for_user(
            user["id"],
            workspace_id,
        )
        authorization = resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace["id"],
        )
    except (PermissionError, ValueError, AuthorizationError) as exc:
        raise HTTPException(
            404,
            detail={
                "code": "workspace_unavailable",
                "message": "Workspace is unavailable.",
            },
        ) from exc

    try:
        authorization.require(permission)
    except AuthorizationError as exc:
        raise HTTPException(
            403,
            detail={
                "code": "permission_denied",
                "message": "You do not have permission to perform this action.",
            },
        ) from exc

    return workspace



def request_user_id(request: Request) -> str:
    """Return the authenticated request principal resolved by the permission gate."""

    user_id = getattr(request.state, "authenticated_user_id", None)
    if user_id:
        return user_id

    user, _ = auth._authenticated_record(request)
    request.state.authenticated_user_id = user["id"]
    return user["id"]

def resolve_request_workspace(
    request: Request,
    workspace_id: str | None = None,
):
    """Backward-compatible workspace resolver enforcing basic view access."""

    return require_request_permission(
        request,
        workspace_id,
        Permission.WORKSPACE_VIEW,
    )


@router.get(
    "",
    response_model=WorkspaceListResponse,
)
async def list_workspaces(request: Request):
    """List only workspaces visible to the authenticated user."""

    user, _ = auth._authenticated_record(request)

    personal = repository.ensure_personal_workspace(
        user["id"]
    )

    organizations = []

    for membership in (
        repository.list_organization_memberships_for_user(
            user["id"],
            active_only=True,
        )
    ):
        workspace = repository.get_workspace(
            membership["workspace_id"], user_id=user["id"],
        )

        if (
            workspace is None
            or not workspace["active"]
            or workspace["kind"] != "organization"
        ):
            continue

        organizations.append(
            WorkspaceSummary(
                id=workspace["id"],
                kind="organization",
                name=workspace["name"],
                membership_role=membership[
                    "membership_role"
                ],
            )
        )

    return WorkspaceListResponse(
        personal_workspace=WorkspaceSummary(
            id=personal["id"],
            kind="personal",
            name=personal["name"],
            membership_role=None,
        ),
        organizations=organizations,
    )


@router.post(
    "/organizations",
    response_model=OrganizationCreated,
    status_code=201,
)
async def create_organization(
    payload: CreateOrganizationRequest,
    request: Request,
):
    """Create a private-by-default Organization workspace.

    No organization directory or discovery endpoint exists.
    """

    user, _ = auth._authenticated_record(
        request
    )

    try:
        workspace, join_code = (
            repository.create_organization(
                creator_user_id=user["id"],
                name=payload.name,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            400,
            detail={
                "code": "invalid_organization",
                "message": str(exc),
            },
        ) from exc

    return OrganizationCreated(
        id=workspace["id"],
        name=workspace["name"],
        join_code=join_code,
    )



@router.post(
    "/organizations/join",
    response_model=OrganizationJoined,
)
async def join_organization(
    payload: JoinOrganizationRequest,
    request: Request,
):
    """Join exactly one Organization by non-public share code.

    No Organization search, directory, count, or discovery is performed.
    """

    user, _ = auth._authenticated_record(
        request
    )

    try:
        workspace, membership = (
            repository.join_organization(
                user_id=user["id"],
                join_code=payload.join_code,
            )
        )

    except LookupError as exc:
        # Intentionally generic. Do not reveal whether any Organization
        # exists behind an invalid/inactive code.
        raise HTTPException(
            404,
            detail={
                "code": "invalid_join_code",
                "message": (
                    "The organization join code is invalid or unavailable."
                ),
            },
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            400,
            detail={
                "code": "join_organization_failed",
                "message": str(exc),
            },
        ) from exc

    return OrganizationJoined(
        id=workspace["id"],
        name=workspace["name"],
        membership_role=membership[
            "membership_role"
        ],
    )


@router.get(
    "/organizations/{workspace_id}/members",
    response_model=OrganizationMemberListResponse,
)
async def list_organization_members(
    workspace_id: str,
    request: Request,
):
    """List active members for an organization when RBAC permits it."""

    user, _ = auth._authenticated_record(request)

    try:
        authorization = resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            404,
            detail={
                "code": "workspace_unavailable",
                "message": "Workspace is unavailable.",
            },
        ) from exc

    try:
        authorization.require(Permission.ORGANIZATION_MEMBERS_VIEW)
    except AuthorizationError as exc:
        raise HTTPException(
            403,
            detail={
                "code": "permission_denied",
                "message": "You do not have permission to view organization members.",
            },
        ) from exc

    members = []
    for membership in repository.list_organization_memberships(
        workspace_id,
        active_only=True,
        actor_user_id=user["id"],
    ):
        member_user = repository.get_user(membership["user_id"])
        if member_user is None or not member_user["active"]:
            continue

        members.append(
            OrganizationMemberSummary(
                user_id=member_user["id"],
                display_name=member_user["display_name"],
                email=member_user["email"],
                profile_picture=member_user.get("profile_picture"),
                membership_role=membership["membership_role"],
                joined_at=membership["joined_at"],
            )
        )

    return OrganizationMemberListResponse(
        workspace_id=workspace_id,
        members=members,
    )


@router.patch(
    "/organizations/{workspace_id}/members/{target_user_id}/role",
    response_model=OrganizationMemberRoleChanged,
)
async def change_organization_member_role(
    workspace_id: str,
    target_user_id: str,
    payload: ChangeOrganizationMemberRoleRequest,
    request: Request,
):
    """Change one active organization member role under repository safeguards."""

    user, _ = auth._authenticated_record(request)

    try:
        resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            404,
            detail={
                "code": "workspace_unavailable",
                "message": "Workspace is unavailable.",
            },
        ) from exc

    try:
        membership = repository.change_organization_membership_role(
            workspace_id=workspace_id,
            actor_user_id=user["id"],
            target_user_id=target_user_id,
            new_role=payload.membership_role,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            403,
            detail={
                "code": "permission_denied",
                "message": "You do not have permission to change this member role.",
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            409,
            detail={
                "code": "role_change_conflict",
                "message": str(exc),
            },
        ) from exc

    return OrganizationMemberRoleChanged(
        workspace_id=workspace_id,
        user_id=membership["user_id"],
        membership_role=membership["membership_role"],
    )

@router.get(
    "/organizations/{workspace_id}/human-roles",
    response_model=OrganizationHumanRoleListResponse,
)
async def list_organization_human_roles(
    workspace_id: str,
    request: Request,
):
    user, _ = auth._authenticated_record(request)

    try:
        authorization = resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            404,
            detail={"code": "workspace_unavailable", "message": "Workspace is unavailable."},
        ) from exc

    try:
        authorization.require(Permission.ORGANIZATION_HUMAN_ROLES_MANAGE)
    except AuthorizationError as exc:
        raise HTTPException(
            403,
            detail={"code": "permission_denied", "message": "You do not have permission to manage HR human roles."},
        ) from exc

    try:
        rows = repository.list_organization_human_roles(
            workspace_id, active_only=True, actor_user_id=user["id"],
        )
    except AuthorizationError as exc:
        # A membership/role can change between initial checks and the scoped
        # read. Preserve inaccessible-workspace 404 versus missing-permission 403.
        try:
            resolve_workspace_authorization(repository, user_id=user["id"], workspace_id=workspace_id)
        except AuthorizationError:
            raise HTTPException(
                404, detail={"code": "workspace_unavailable", "message": "Workspace is unavailable."},
            ) from exc
        raise HTTPException(
            403, detail={"code": "permission_denied", "message": "You do not have permission to manage HR human roles."},
        ) from exc

    assignments = [
        OrganizationHumanRoleAssignment(
            user_id=row["user_id"],
            human_role=row["human_role"],
        )
        for row in rows
    ]
    return OrganizationHumanRoleListResponse(
        workspace_id=workspace_id,
        assignments=assignments,
    )


@router.post(
    "/organizations/{workspace_id}/members/{target_user_id}/human-roles",
    response_model=OrganizationHumanRoleChanged,
    status_code=201,
)
async def assign_organization_human_role(
    workspace_id: str,
    target_user_id: str,
    payload: AssignOrganizationHumanRoleRequest,
    request: Request,
):
    user, _ = auth._authenticated_record(request)

    try:
        resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            404,
            detail={"code": "workspace_unavailable", "message": "Workspace is unavailable."},
        ) from exc

    try:
        assignment = repository.assign_organization_human_role(
            workspace_id=workspace_id,
            actor_user_id=user["id"],
            target_user_id=target_user_id,
            human_role=payload.human_role,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            403,
            detail={"code": "permission_denied", "message": "You do not have permission to assign this HR human role."},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            409,
            detail={"code": "human_role_conflict", "message": str(exc)},
        ) from exc

    return OrganizationHumanRoleChanged(
        workspace_id=workspace_id,
        user_id=assignment["user_id"],
        human_role=assignment["human_role"],
        active=True,
    )


@router.delete(
    "/organizations/{workspace_id}/members/{target_user_id}/human-roles/{human_role}",
    response_model=OrganizationHumanRoleChanged,
)
async def deactivate_organization_human_role(
    workspace_id: str,
    target_user_id: str,
    human_role: str,
    request: Request,
):
    user, _ = auth._authenticated_record(request)

    try:
        resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            404,
            detail={"code": "workspace_unavailable", "message": "Workspace is unavailable."},
        ) from exc

    try:
        assignment = repository.deactivate_organization_human_role(
            workspace_id=workspace_id,
            actor_user_id=user["id"],
            target_user_id=target_user_id,
            human_role=human_role,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            403,
            detail={"code": "permission_denied", "message": "You do not have permission to change this HR human role."},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            422,
            detail={"code": "invalid_human_role", "message": str(exc)},
        ) from exc

    if assignment is None:
        raise HTTPException(
            404,
            detail={"code": "human_role_assignment_not_found", "message": "HR human role assignment was not found."},
        )

    return OrganizationHumanRoleChanged(
        workspace_id=workspace_id,
        user_id=assignment["user_id"],
        human_role=assignment["human_role"],
        active=False,
    )
