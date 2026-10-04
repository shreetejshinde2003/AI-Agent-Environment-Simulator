"""Persisted, run-scoped agent handoffs."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Header, Query, Request
from app.models.schemas import Message, MessageKind, Task
from app.storage.database import repository
from app.api.routes.workspaces import require_request_permission, request_user_id
from app.websocket.manager import manager
from app.security.rbac import Permission

router = APIRouter(prefix="/messages", tags=["messages"])


async def record_message(from_agent_id: str, to_agent_id: str, kind: MessageKind,
                         content: str, *, task: Task, output_key: str, user_id: str | None = None):
    message = Message(id=f"m-{uuid.uuid4().hex}", from_agent_id=from_agent_id,
                      to_agent_id=to_agent_id, kind=kind, content=content,
                      timestamp=datetime.now(timezone.utc), simulation_id=task.id,
                      output_key=output_key)
    task.messages.append(message)
    if user_id is not None and task.workspace_id is not None:
        repository.save_for_tenant(
            task, workspace_id=task.workspace_id, user_id=user_id
        )
    else:
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
    workspace = require_request_permission(
        request, x_workspace_id, Permission.SIMULATION_VIEW
    )
    user_id = request_user_id(request)
    runs = (
        [repository.get_for_tenant(
            simulation_id, workspace_id=workspace["id"], user_id=user_id
        )]
        if simulation_id
        else repository.list_for_tenant(
            workspace_id=workspace["id"], user_id=user_id
        )
    )
    messages = [m for run in runs if run for m in run.messages]
    return sorted(messages, key=lambda m: m.timestamp)[-limit:]


def get_message_count():
    return sum(len(run.messages) for run in repository.list())
