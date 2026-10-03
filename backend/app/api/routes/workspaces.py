"""Organization workspace endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.api.routes import auth
from app.models.schemas import (
    CreateOrganizationRequest,
    OrganizationCreated,
)
from app.storage.database import repository


router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
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
