"""Workspace-scoped WebSocket connection manager."""

import json
from datetime import datetime, timezone
from collections.abc import Callable

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: dict[WebSocket, str] = {}
        self._authorizers: dict[WebSocket, Callable[[], None]] = {}

    async def connect(self, websocket: WebSocket, workspace_id: str, *, authorize: Callable[[], None] | None = None) -> None:
        await websocket.accept()
        self._active_connections[websocket] = workspace_id
        if authorize is not None:
            self._authorizers[websocket] = authorize

    def disconnect(self, websocket: WebSocket) -> None:
        self._active_connections.pop(websocket, None)
        self._authorizers.pop(websocket, None)

    async def authorized(self, websocket: WebSocket) -> bool:
        authorize = self._authorizers.get(websocket)
        if authorize is not None:
            try:
                authorize()
            except Exception:
                # Revoked/expired identities and unavailable authorization storage
                # cannot continue to receive tenant evidence. Never send diagnostics.
                self.disconnect(websocket)
                try:
                    await websocket.close(code=4404)
                except Exception:
                    pass
                return False
        return websocket in self._active_connections

    async def broadcast(
        self,
        event_type: str,
        payload: dict,
        *,
        workspace_id: str | None = None,
    ) -> None:
        """Broadcast globally or, for tenant data, only within one workspace."""
        message = json.dumps(
            {
                "event": event_type,
                "data": payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        for connection, connection_workspace_id in list(
            self._active_connections.items()
        ):
            if (
                workspace_id is not None
                and connection_workspace_id != workspace_id
            ):
                continue
            if not await self.authorized(connection):
                continue
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


manager = ConnectionManager()
