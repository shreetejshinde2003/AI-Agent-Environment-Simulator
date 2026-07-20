"""
app/websocket/manager.py

Broadcasts live updates to every connected dashboard client. This class is
fully functional as-is — it doesn't depend on storage or agents/ being
implemented yet.

How it gets used later:
    - app/api/routes/*.py will call `manager.broadcast(...)` after any
      state change (task created, agent status changed, message sent).
    - app/agents/orchestrator.py (RESERVED, LangGraph) will call
      `manager.broadcast(...)` on every node transition, which is what
      actually drives the "Live" badges and Simulation Timeline on the
      frontend.
"""

import json
from datetime import datetime, timezone

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)

    async def broadcast(self, event_type: str, payload: dict) -> None:
        """
        Send a JSON event to every connected client.

        event_type examples the frontend should expect (keep this list in
        sync with whatever useLiveSocket.js switches on):
            "agent_status_changed" | "task_updated" | "task_created" |
            "message_sent" | "activity_event" | "stats_updated"
        """
        message = json.dumps(
            {
                "event": event_type,
                "data": payload,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Iterate over a copy — a client can disconnect mid-broadcast
        for connection in list(self._active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                # Client dropped without a clean close handshake — prune it.
                self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


# Single shared instance — import this everywhere, don't instantiate a new one.
manager = ConnectionManager()
