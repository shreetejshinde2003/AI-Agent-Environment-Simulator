"""
app/api/routes/messages.py

Endpoints for the Messages page and the "Message Flow (Live)" card on
the dashboard.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import Message, MessageKind

router = APIRouter(prefix="/messages", tags=["messages"])


# ----------------------------------------------------------------------
# TEMPORARY in-memory mock data — replace with DB query once storage
# is activated.
# ----------------------------------------------------------------------
_MOCK_MESSAGES: list[Message] = [
    Message(
        id="m1", from_agent_id="research", to_agent_id="data", kind=MessageKind.REQUEST,
        content="Please extract structured data from sources", timestamp=datetime.now(timezone.utc),
    ),
    Message(
        id="m2", from_agent_id="data", to_agent_id="analysis", kind=MessageKind.RESPONSE,
        content="Extracted 42 records successfully", timestamp=datetime.now(timezone.utc),
    ),
    Message(
        id="m3", from_agent_id="analysis", to_agent_id="summarizer", kind=MessageKind.REQUEST,
        content="Please generate insights summary", timestamp=datetime.now(timezone.utc),
    ),
    Message(
        id="m4", from_agent_id="summarizer", to_agent_id="report", kind=MessageKind.RESPONSE,
        content="Summary generated. Preparing report.", timestamp=datetime.now(timezone.utc),
    ),
]


@router.get("", response_model=list[Message])
async def list_messages(limit: int = 50):
    """GET /api/v1/messages — powers the Messages page and Message Flow card.

    `limit` param: RESERVED for pagination once message volume grows —
    harmless no-op against mock data today, but wire it into the real
    DB query (ORDER BY timestamp DESC LIMIT :limit) once storage exists.
    """
    return _MOCK_MESSAGES[-limit:]
