from __future__ import annotations

from html import escape

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from src.aris_apps.aiida.paths import logs_template
from src.aris_core.logging import get_log_buffer_snapshot, log_event
from loguru import logger

router = APIRouter(tags=["aiida-root"])


class SessionTitleUpdateRequest(BaseModel):
    title: str | None = None


@router.put("/api/sessions/{session_id}/title")
async def update_session_title(request: Request, session_id: str, payload: SessionTitleUpdateRequest):
    from src.aris_apps.aiida.chat import (
        get_active_chat_project_id,
        get_active_chat_session_id,
        get_chat_snapshot,
        list_chat_projects,
        update_chat_session,
    )

    state = request.app.state
    session = update_chat_session(state, session_id, title=payload.title)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return {
        "session": session,
        "chat": get_chat_snapshot(state),
        "active_session_id": get_active_chat_session_id(state),
        "active_project_id": get_active_chat_project_id(state),
        "projects": list_chat_projects(state),
        "version": int(getattr(state, "chat_sessions_version", 0)),
    }


@router.get("/api/specializations/active")
async def specializations_active(
    context_node_ids: list[int] | None = Query(default=None),
    project_tags: list[str] | None = Query(default=None),
    resource_plugins: list[str] | None = Query(default=None),
    selected_environment: str | None = Query(default=None),
    auto_switch: bool = Query(default=True),
):
    from src.aris_apps.aiida.specializations import build_active_specializations_payload

    return await build_active_specializations_payload(
        context_node_ids=context_node_ids,
        project_tags=project_tags,
        resource_plugins=resource_plugins,
        selected_environment=selected_environment,
        auto_switch=auto_switch,
    )


@router.get("/api/aiida/logs/copy", response_class=HTMLResponse)
async def aiida_logs_copy_page():
    _, lines = get_log_buffer_snapshot(limit=240)
    payload = "\n".join(lines[-120:]) if lines else "No logs yet."
    safe_payload = escape(payload)
    template_path = logs_template()

    try:
        template = template_path.read_text(encoding="utf-8")
        html = template.replace("{{safe_payload}}", safe_payload)
        return HTMLResponse(html)
    except Exception as exc:  # noqa: BLE001
        logger.error(log_event("aiida.logs.template.missing", path=str(template_path), error=str(exc)))
        return HTMLResponse(f"<html><body><pre>{safe_payload}</pre></body></html>")
