"""
app/api/routes/messages.py

Endpoints for the Messages page and the "Message Flow (Live)" card on
the dashboard.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import Message, MessageKind
from app.websocket.manager import manager

router = APIRouter(prefix="/messages", tags=["messages"])


# ----------------------------------------------------------------------
# Real message log — starts empty (not fake pre-populated conversation
# history). Replace with a DB query once storage is activated.
# RESERVED: currently nothing calls record_message() yet — wire it into
# api/routes/tasks.py's _run_task() once multiple agents hand off to
# each other (right now there's only one real agent, so there's no
# real agent-to-agent message to log — a single agent completing a
# task is captured as an ActivityEvent, not a Message).
# ----------------------------------------------------------------------
_MESSAGES: list[Message] = []


async def record_message(from_agent_id: str, to_agent_id: str, kind: MessageKind, content: str) -> None:
    """Call this once a real agent hands off to another agent."""
    message = Message(
        id=f"m-{uuid.uuid4().hex[:8]}",
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        kind=kind,
        content=content,
        timestamp=datetime.now(timezone.utc),
    )
    _MESSAGES.append(message)
    await manager.broadcast("message_sent", message.model_dump(mode="json"))


@router.get("", response_model=list[Message])
async def list_messages(limit: int = 50):
    """GET /api/v1/messages — powers the Messages page and Message Flow card.

    `limit` param: RESERVED for pagination once message volume grows —
    harmless no-op against in-memory data today, but wire it into the
    real DB query (ORDER BY timestamp DESC LIMIT :limit) once storage exists.
    """
    return _MESSAGES[-limit:]


def get_message_count() -> int:
    """Used by api/routes/simulation.py to compute totalMessages live —
    kept as a function (not a direct import of _MESSAGES) so this
    module stays the one source of truth for what counts as a message."""
    return len(_MESSAGES)
