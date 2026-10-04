"""
app/main.py

FastAPI application entrypoint. Run with:
    uvicorn app.main:app --reload

or via the convenience script:
    python run.py
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
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

@asynccontextmanager
async def lifespan(app):
    repository.initialize()
    tasks.recover_interrupted()
    yield


app = FastAPI(title=settings.APP_NAME, debug=False, lifespan=lifespan)

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
    workspace_id = websocket.query_params.get("workspaceId")

    try:
        user, _ = auth._authenticated_record(websocket)
        workspace = repository.resolve_workspace_for_user(
            user["id"],
            workspace_id,
        )
    except HTTPException:
        await websocket.close(code=4401)
        return
    except (PermissionError, ValueError):
        await websocket.close(code=4404)
        return

    await manager.connect(websocket, workspace["id"])
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
