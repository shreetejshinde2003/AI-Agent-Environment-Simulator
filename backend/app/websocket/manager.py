"""Workspace-scoped WebSocket connection manager."""

import json
from datetime import datetime, timezone

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, workspace_id: str) -> None:
        await websocket.accept()
        self._active_connections[websocket] = workspace_id

    def disconnect(self, websocket: WebSocket) -> None:
        self._active_connections.pop(websocket, None)

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
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


manager = ConnectionManager()
