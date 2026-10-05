"""Bounded UTF-8 uploads; parsed as data and never executed."""
import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import PurePath

from fastapi import APIRouter, Header, HTTPException, Request
from app.models.schemas import UploadedContext
from app.security.rbac import Permission
from app.storage.database import repository
from app.api.routes.workspaces import require_request_permission, request_user_id

router = APIRouter(prefix="/uploads", tags=["uploads"])
MAX_BYTES = 256 * 1024
MAX_CONTEXT = 6000


def parse_upload(filename: str, content: bytes):
    name = PurePath(filename.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:100]
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in {"txt", "csv", "json"}:
        raise HTTPException(415, "Only TXT, CSV and JSON are supported")
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(413, "Upload must contain 1–262144 bytes")
    try:
        text = content.decode("utf-8-sig")
        if "\x00" in text:
            raise ValueError("Binary data is not supported")
        rows, columns = None, []
        if extension == "json":
            parsed = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            prepared = json.dumps(parsed, ensure_ascii=False, indent=2)
        elif extension == "csv":
            records = list(csv.reader(io.StringIO(text), strict=True))
            if not records or not records[0] or any(len(row) != len(records[0]) for row in records):
                raise ValueError("Inconsistent CSV rows")
            columns, rows = records[0], len(records)-1
            output = io.StringIO()
            csv.writer(output).writerows(records[:21])
            prepared = output.getvalue()
        else:
            prepared = text
    except (UnicodeError, ValueError, csv.Error, RecursionError):
        raise HTTPException(422, "Cannot parse file: use valid UTF-8 TXT, rectangular CSV or JSON")
    truncated = len(prepared) > MAX_CONTEXT or (extension == "csv" and rows > 20)
    prepared = prepared[:MAX_CONTEXT]
    if truncated:
        prepared += "\n[Context truncated: only the preview above is supplied to agents.]"
    return UploadedContext(
        id=f"U-{uuid.uuid4().hex}", filename=name, format=extension,
        size_bytes=len(content), created_at=datetime.now(timezone.utc),
        preview=prepared, prepared_context=prepared, truncated=truncated,
        row_count=rows, columns=columns[:100],
    )


@router.post("", status_code=201)
async def upload_context(
    request: Request,
    filename: str,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
):
    workspace = require_request_permission(
        request,
        x_workspace_id,
        Permission.SIMULATION_CREATE,
    )
    user_id = request_user_id(request)
    # Raw File request avoids an additional multipart dependency and permits
    # enforcing the byte limit while streaming, before buffering the full body.
    allowed_types = {"text/plain", "text/csv", "application/json", "application/octet-stream",
                     "application/vnd.ms-excel", ""}
    content_type = request.headers.get("content-type", "").split(";")[0]
    if content_type not in allowed_types:
        raise HTTPException(415, "Unsupported content type")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Maximum upload size is 256 KiB")
        data.extend(chunk)
    upload = parse_upload(filename, bytes(data))
    repository.save_upload_for_tenant(
        upload,
        workspace_id=workspace["id"],
        user_id=user_id,
    )
    return upload


@router.get("/{upload_id}")
async def get_upload(
    upload_id: str,
    request: Request,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
):
    workspace = require_request_permission(
        request,
        x_workspace_id,
        Permission.SIMULATION_VIEW,
    )
    upload = repository.get_upload_for_tenant(
        upload_id,
        workspace_id=workspace["id"],
        user_id=request_user_id(request),
    )
    if upload is None:
        raise HTTPException(404, "Upload not found")
    return upload
