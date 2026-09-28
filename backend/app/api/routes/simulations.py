"""Simulation projection of compatible tasks, metrics and real exports."""
import csv
import io
import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from app.api.routes.tasks import create_task, get_record
from app.api.routes.simulation import aggregate
from app.models.schemas import CreateSimulationRequest
from app.storage.database import repository

router = APIRouter(prefix="/simulations", tags=["simulations"])


def view(task):
    result = task.model_dump(mode="json")
    result["status"] = "running" if task.status.value == "in_progress" else task.status.value
    return result


@router.get("")
async def list_simulations():
    return [view(task) for task in repository.list()]


@router.post("", status_code=201)
async def create_simulation(payload: CreateSimulationRequest, background_tasks: BackgroundTasks):
    return view(await create_task(payload, background_tasks))


@router.get("/metrics")
async def metrics():
    runs = repository.list()
    by_agent = []
    for agent_id in ("research", "data", "analysis", "summarizer", "report"):
        stages = [s for r in runs for s in r.stages if s.agent_id == agent_id and s.started_at]
        stages.sort(key=lambda s: s.started_at)
        measured = [s for s in stages if s.total_tokens is not None]
        times = [s.duration_seconds for s in stages if s.duration_seconds is not None]
        by_agent.append(dict(
            agentId=agent_id, calls=len(stages),
            completed=sum(s.status == "completed" for s in stages),
            failed=sum(s.status == "failed" for s in stages),
            totalTokens=sum(s.total_tokens for s in measured),
            measuredCalls=len(measured),
            averageTokens=sum(s.total_tokens for s in measured)/len(measured) if measured else None,
            averageLatency=sum(times)/len(times) if times else None,
            lastExecution=stages[-1].model_dump(mode="json") if stages else None,
        ))
    return {"summary": aggregate(), "agents": by_agent, "history": [
        dict(id=r.id, createdAt=(r.created_at or r.started_at).isoformat(), status=r.status.value,
             duration=r.elapsed_seconds,
             tokens=sum(s.total_tokens for s in r.stages if s.total_tokens is not None))
        for r in runs
    ]}


@router.get("/{simulation_id}")
async def get_simulation(simulation_id: str):
    return view(get_record(simulation_id))


@router.get("/{simulation_id}/events")
async def events(simulation_id: str):
    return get_record(simulation_id).events


def csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@router.get("/{simulation_id}/export")
async def export_simulation(simulation_id: str, format: str = "json"):
    task = get_record(simulation_id)
    if task.status.value not in ("completed", "failed"):
        raise HTTPException(409, "Export is available after the simulation finishes")
    if format == "json":
        content = json.dumps(view(task), ensure_ascii=False, indent=2)
        media = "application/json"
    elif format == "txt":
        content = f"Simulation {task.id}\nDirective: {task.directive}\nStatus: {task.status.value}\n\n"
        content += task.output or task.error or ""
        media = "text/plain"
    elif format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["agent", "status", "model", "seconds", "input_tokens", "output_tokens", "total_tokens", "error"])
        for s in task.stages:
            writer.writerow([csv_safe(v) for v in (s.agent_id, s.status, s.model, s.duration_seconds,
                                                  s.input_tokens, s.output_tokens, s.total_tokens, s.error)])
        content, media = buffer.getvalue(), "text/csv"
    else:
        raise HTTPException(422, "Supported formats: txt, json, csv")
    return Response(content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{task.id}.{format}"'})
