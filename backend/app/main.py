"""
app/main.py

FastAPI application entrypoint. Run with:
    uvicorn app.main:app --reload

or via the convenience script:
    python run.py
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, messages, simulation, tasks, simulations, uploads
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
app.include_router(agents.router, prefix=settings.API_V1_PREFIX)
app.include_router(tasks.router, prefix=settings.API_V1_PREFIX)
app.include_router(messages.router, prefix=settings.API_V1_PREFIX)
app.include_router(simulation.router, prefix=settings.API_V1_PREFIX)
app.include_router(simulations.router, prefix=settings.API_V1_PREFIX)
app.include_router(uploads.router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    """Simple liveness check — hit this first when debugging connectivity."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.websocket(settings.WEBSOCKET_PATH)
async def websocket_endpoint(websocket: WebSocket):
    """
    Live update stream — the frontend's hooks/useLiveSocket.js connects
    here. Every broadcast from manager.broadcast(...) (called from the
    sequential task coordinator) gets
    pushed to every connected client.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect the frontend to send anything meaningful yet;
            # this just keeps the connection alive and detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
