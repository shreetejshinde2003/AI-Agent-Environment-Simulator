"""Workspace-scoped simulation recycle bin; no automatic expiry or purge."""
from fastapi import APIRouter, Header, HTTPException, Request

from app.api.routes.workspaces import require_request_permission, request_user_id
from app.models.schemas import PermanentDeletionRequest
from app.security.rbac import AuthorizationError, Permission
from app.storage.database import RecycleBinError, repository

router = APIRouter(tags=["recycle-bin"])


def translate_operation(operation):
    try:
        return operation()
    except RecycleBinError as exc:
        raise HTTPException(exc.status_code, detail=exc.detail) from exc
    except AuthorizationError as exc:
        raise HTTPException(403, detail={"code": "permission_denied",
                            "message": "You do not have permission to perform this action."}) from exc


@router.get("/recycle-bin")
async def list_deleted(request: Request, x_workspace_id: str | None = Header(default=None)):
    workspace = require_request_permission(request, x_workspace_id, Permission.RECYCLE_BIN_MANAGE)
    return translate_operation(lambda: repository.list_recycled_simulations(
        workspace_id=workspace["id"], user_id=request_user_id(request)))


@router.delete("/simulations/{simulation_id}")
async def soft_delete(simulation_id: str, request: Request,
                      x_workspace_id: str | None = Header(default=None)):
    workspace = require_request_permission(request, x_workspace_id, Permission.RECYCLE_BIN_MANAGE)
    return translate_operation(lambda: repository.recycle_simulation(simulation_id,
        workspace_id=workspace["id"], user_id=request_user_id(request)))


@router.post("/recycle-bin/simulations/{simulation_id}/restore")
async def restore(simulation_id: str, request: Request,
                  x_workspace_id: str | None = Header(default=None)):
    workspace = require_request_permission(request, x_workspace_id, Permission.RECYCLE_BIN_MANAGE)
    return translate_operation(lambda: repository.recycle_simulation(simulation_id,
        workspace_id=workspace["id"], user_id=request_user_id(request), action="restore"))


@router.delete("/recycle-bin/simulations/{simulation_id}")
async def permanent_delete(simulation_id: str, payload: PermanentDeletionRequest, request: Request,
                           x_workspace_id: str | None = Header(default=None)):
    workspace = require_request_permission(request, x_workspace_id, Permission.RECYCLE_BIN_PURGE)
    return translate_operation(lambda: repository.recycle_simulation(simulation_id,
        workspace_id=workspace["id"], user_id=request_user_id(request), action="purge",
        confirmed=payload.confirm_permanent_deletion))
