"""Organization workspace endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.api.routes import auth
from app.models.schemas import (
    CreateOrganizationRequest,
    JoinOrganizationRequest,
    OrganizationCreated,
    OrganizationJoined,
    WorkspaceListResponse,
    WorkspaceSummary,
)
from app.storage.database import repository


router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
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
            membership["workspace_id"]
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
