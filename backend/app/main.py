"""
app/main.py

FastAPI application entrypoint. Run with:
    uvicorn app.main:app --reload

or via the convenience script:
    python run.py
"""

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    recycle_bin,
    agent_builder,
    agents,
    auth,
    datasets,
    experiments,
    messages,
    simulation,
    tasks,
    simulations,
    uploads,
    workspaces,
)
from app.storage.database import repository
from app.core.config import settings
from app.websocket.manager import manager
from app.security.rbac import AuthorizationError, Permission, resolve_workspace_authorization
from app.security.browser_origin import BrowserOriginMiddleware, trusted_browser_request

@asynccontextmanager
async def lifespan(app):
    # PG initialization activates the ready data plane and user-bound bootstrap;
    # recovery then uses workspace-scoped locked maintenance transactions.
    repository.initialize()
    tasks.recover_interrupted()
    yield


app = FastAPI(title=settings.APP_NAME, debug=False, lifespan=lifespan)
app.add_middleware(BrowserOriginMiddleware)

# --------------------------------------------------------------------
# CORS — allowed origins are defined in app/core/config.py, NOT here.
# Update settings.CORS_ORIGINS when the frontend's dev port or deployed
# URL changes.
# --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------
# Routers — each one is namespaced under API_V1_PREFIX (see config.py)
# --------------------------------------------------------------------
app.include_router(agent_builder.router, prefix=settings.API_V1_PREFIX)
app.include_router(recycle_bin.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(workspaces.router, prefix=settings.API_V1_PREFIX)
app.include_router(agents.router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks.router, prefix=settings.API_V1_PREFIX)
app.include_router(messages.router, prefix=settings.API_V1_PREFIX)
app.include_router(simulation.router, prefix=settings.API_V1_PREFIX)
app.include_router(simulations.router, prefix=settings.API_V1_PREFIX)
app.include_router(uploads.router, prefix=settings.API_V1_PREFIX)
app.include_router(datasets.router, prefix=settings.API_V1_PREFIX)
app.include_router(experiments.router, prefix=settings.API_V1_PREFIX)

@app.get("/health")
async def health_check():
    """Simple liveness check — hit this first when debugging connectivity."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.websocket(settings.WEBSOCKET_PATH)
async def websocket_endpoint(websocket: WebSocket):
    """Authenticated live stream scoped to one accessible workspace."""
    if not trusted_browser_request(websocket.headers):
        await websocket.close(code=4403)
        return
    workspace_id = websocket.query_params.get("workspaceId")

    try:
        user, _ = auth._authenticated_record(websocket)
        workspace = repository.resolve_workspace_for_user(
            user["id"],
            workspace_id,
        )
        authorization = resolve_workspace_authorization(
            repository,
            user_id=user["id"],
            workspace_id=workspace["id"],
        )
        authorization.require(Permission.WORKSPACE_VIEW)
    except HTTPException:
        await websocket.close(code=4401)
        return
    except (PermissionError, ValueError, AuthorizationError):
        await websocket.close(code=4404)
        return

    def authorize_live_connection():
        current_user, _ = auth._authenticated_record(websocket)
        if current_user["id"] != user["id"]:
            raise AuthorizationError("Permission denied.")
        resolve_workspace_authorization(repository, user_id=current_user["id"],
            workspace_id=workspace["id"]).require(Permission.WORKSPACE_VIEW)

    await manager.connect(websocket, workspace["id"], authorize=authorize_live_connection)
    try:
        while await manager.authorized(websocket):
            try:
                # Idle sockets also lose revoked authority within 30 seconds;
                # every outgoing event performs another live check before sending.
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
