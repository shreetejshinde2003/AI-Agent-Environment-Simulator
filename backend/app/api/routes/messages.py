"""Persisted, run-scoped agent handoffs."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Header, Query, Request
from app.models.schemas import Message, MessageKind, Task
from app.storage.database import repository
from app.api.routes.workspaces import resolve_request_workspace
from app.websocket.manager import manager

router = APIRouter(prefix="/messages", tags=["messages"])


async def record_message(from_agent_id: str, to_agent_id: str, kind: MessageKind,
                         content: str, *, task: Task, output_key: str):
    message = Message(id=f"m-{uuid.uuid4().hex}", from_agent_id=from_agent_id,
                      to_agent_id=to_agent_id, kind=kind, content=content,
                      timestamp=datetime.now(timezone.utc), simulation_id=task.id,
                      output_key=output_key)
    task.messages.append(message)
    repository.save(task)
    await manager.broadcast(
        "message_sent",
        message.model_dump(mode="json"),
        workspace_id=task.workspace_id,
    )
    return message


@router.get("", response_model=list[Message])
async def list_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=1000),
    simulation_id: str | None = None,
    x_workspace_id: str | None = Header(default=None),
):
    workspace = resolve_request_workspace(request, x_workspace_id)
    runs = (
        [repository.get_for_workspace(simulation_id, workspace["id"])]
        if simulation_id
        else repository.list_for_workspace(workspace["id"])
    )
    messages = [m for run in runs if run for m in run.messages]
    return sorted(messages, key=lambda m: m.timestamp)[-limit:]


def get_message_count():
    return sum(len(run.messages) for run in repository.list())
