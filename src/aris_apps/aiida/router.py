from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pprint import pformat
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import APIRouter, File, Form, HTTPException, Path as ApiPath, Query, Request, UploadFile
from fastapi.responses import Response
from google import genai
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from src.aris_core.config import settings
from src.aris_core.logging import get_log_buffer_snapshot, log_event

from .chat import (
    activate_chat_session,
    cancel_chat_turn,
    create_chat_project,
    create_chat_session,
    delete_chat_items,
    get_active_chat_project_id,
    get_active_chat_session_id,
    get_chat_history,
    get_chat_session_detail,
    get_chat_session_batch_progress,
    get_chat_session_workspace_path,
    get_chat_snapshot,
    list_chat_projects,
    list_chat_project_workspace_files,
    list_chat_session_workspace_files,
    list_chat_sessions,
    normalize_context_node_ids,
    serialize_chat_history,
    start_chat_turn,
    update_chat_session,
)
from .bridge_client import bridge_endpoint
from .client import (
    BridgeAPIError,
    BridgeOfflineError,
    build_bridge_context_headers,
    bridge_service,
    request_json,
)
from .presenters.node_view import (
    attach_tree_links as _attach_tree_links,
    enrich_process_detail_payload as _enrich_process_detail_payload,
    extract_folder_preview as _extract_folder_preview,
    serialize_groups as _serialize_groups,
    serialize_processes as _serialize_processes,
    extract_node_hover_metadata as _extract_node_hover_metadata,
    _coerce_chat_metadata,
)
from .presenters.workflow_view import (
    extract_submitted_pk as _extract_submitted_pk,
    enrich_submission_draft_payload,
    format_single_submission_response,
    format_worker_batch_submission_response,
)
from .service import (
    add_nodes_to_group,
    create_group,
    delete_group,
    export_group_archive,
    get_context_nodes,
    get_recent_nodes,
    list_groups,
    rename_group,
    soft_delete_node,
    hub,
    parse_infrastructure_via_ai as _parse_infrastructure_via_ai,
)
from .specializations import build_active_specializations_payload
from .infrastructure_manager import infrastructure_manager
from .schemas import (
    FrontendChatRequest,
    FrontendStopChatRequest,
    FrontendChatDeleteRequest,
    FrontendChatProjectCreateRequest,
    FrontendChatSessionCreateRequest,
    FrontendChatSessionTitleUpdateRequest,
    FrontendChatSessionUpdateRequest,
    SubmissionDraftRequest,
    SystemCountsResponse,
    BridgeStatusResponse,
    BridgeSystemInfoResponse,
    BridgeResourcesResponse,
    BridgeProfilesResponse,
    BridgeSwitchProfileRequest,
    BridgeSwitchProfileResponse,
    FrontendGroupCreateRequest,
    FrontendGroupRenameRequest,
    FrontendGroupAssignNodesRequest,
    FrontendNodeSoftDeleteRequest,
    NodeHoverMetadataResponse,
    NodeScriptResponse,
    InfrastructureComputer,
    InfrastructureExportResponse,
    ParseInfrastructureRequest,
    UserInfoResponse,
    ProfileSetupRequest,
    CodeSetupRequest,
    CodeDetailedResponse,
)

FRONTEND_TAG = "AiiDA-Frontend-API"
WORKER_PROXY_TAG = "AiiDA-Worker-Proxy"

router = APIRouter()
DEFAULT_MODELS = [settings.DEFAULT_MODEL]
ARCHIVE_EXTENSIONS = {".aiida", ".zip"}
PENDING_SUBMISSION_KEY = "aiida_pending_submission"


def _get_quick_prompts() -> list[dict[str, str]]:
    """Load quick prompts from external settings file."""
    try:
        settings_path = settings.ARIS_AIIDA_SETTINGS_FILE
        if not os.path.exists(settings_path):
            return []
        with open(settings_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            prompts = data.get("quick_prompts", [])
            return prompts if isinstance(prompts, list) else []
    except Exception as error:
        logger.warning(log_event("aiida.settings.load_failed", error=str(error)))
        return []


def _normalize_text_query_values(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in values or []:
        text = str(raw_value or "").strip()
        if not text:
            continue
        for part in text.split(","):
            candidate = part.strip()
            if not candidate:
                continue
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(candidate)
    return normalized


def _chat_sessions_payload(state: Any) -> dict[str, Any]:
    return {
        "version": int(getattr(state, "chat_sessions_version", 0)),
        "active_session_id": get_active_chat_session_id(state),
        "active_project_id": get_active_chat_project_id(state),
        "projects": list_chat_projects(state),
        "items": list_chat_sessions(state),
    }


def _get_node_hover_metadata(pk: int) -> NodeHoverMetadataResponse:
    if not hub.current_profile:
        hub.start()

    try:
        nodes = get_context_nodes([pk])
    except Exception as error:  # noqa: BLE001
        logger.warning(log_event("aiida.frontend.node_metadata.failed", pk=pk, error=str(error)))
        return NodeHoverMetadataResponse(pk=pk)

    matched: dict[str, Any] | None = None
    for entry in nodes:
        if not isinstance(entry, dict):
            continue
        try:
            entry_pk = int(str(entry.get("pk", "")).strip())
        except (TypeError, ValueError):
            entry_pk = None
        if entry_pk == pk:
            matched = entry
            break
        if matched is None:
            matched = entry

    if not matched:
        return NodeHoverMetadataResponse(pk=pk)

    return _extract_node_hover_metadata(matched, pk)


def _format_python_literal(value: Any) -> str:
    return pformat(value, width=100, sort_dicts=False)


def _build_dict_script_from_summary(payload: dict[str, Any]) -> NodeScriptResponse:
    pk = int(payload.get("pk") or 0)
    attributes = payload.get("attributes")
    data = attributes if isinstance(attributes, dict) else {}
    script = "\n".join(
        [
            f"# Dict PK {pk}",
            f"data = {_format_python_literal(data)}",
            "",
            "# Optional: wrap back into AiiDA",
            "# from aiida.orm import Dict",
            "# data_node = Dict(dict=data)",
        ]
    )
    return NodeScriptResponse(pk=pk, node_type="Dict", language="python", script=script)


def _build_structure_script_from_summary(payload: dict[str, Any]) -> NodeScriptResponse:
    pk = int(payload.get("pk") or 0)
    attributes = payload.get("attributes")
    attrs = attributes if isinstance(attributes, dict) else {}
    preview = payload.get("preview_info") if isinstance(payload.get("preview_info"), dict) else {}
    formula = str(preview.get("formula") or payload.get("label") or f"StructureData #{pk}").strip()

    kind_symbol_map: dict[str, str] = {}
    raw_kinds = attrs.get("kinds")
    if isinstance(raw_kinds, list):
        for item in raw_kinds:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            raw_symbols = item.get("symbols")
            if isinstance(raw_symbols, list) and len(raw_symbols) == 1:
                kind_symbol_map[name] = str(raw_symbols[0])
                continue
            raw_symbol = item.get("symbol")
            if isinstance(raw_symbol, str) and raw_symbol.strip():
                kind_symbol_map[name] = raw_symbol.strip()
                continue
            kind_symbol_map[name] = name

    symbols: list[str] = []
    positions: list[list[float]] = []
    raw_sites = attrs.get("sites")
    if isinstance(raw_sites, list):
        for item in raw_sites:
            if not isinstance(item, dict):
                continue
            kind_name = str(item.get("kind_name") or item.get("kind") or "").strip()
            if not kind_name:
                continue
            raw_position = item.get("position")
            if not isinstance(raw_position, list):
                continue
            symbols.append(kind_symbol_map.get(kind_name, kind_name))
            positions.append([float(coord) for coord in raw_position[:3]])

    cell: list[list[float]] = []
    raw_cell = attrs.get("cell")
    if isinstance(raw_cell, list):
        for row in raw_cell[:3]:
            if isinstance(row, list):
                cell.append([float(coord) for coord in row[:3]])

    pbc = [
        bool(attrs.get("pbc1", True)),
        bool(attrs.get("pbc2", True)),
        bool(attrs.get("pbc3", True)),
    ]

    script = "\n".join(
        [
            f"# StructureData PK {pk}: {formula}",
            "from ase import Atoms",
            "",
            f"symbols = {_format_python_literal(symbols)}",
            f"positions = {_format_python_literal(positions)}",
            f"cell = {_format_python_literal(cell)}",
            f"pbc = {_format_python_literal(pbc)}",
            "",
            "atoms = Atoms(",
            "    symbols=symbols,",
            "    positions=positions,",
            "    cell=cell,",
            "    pbc=pbc,",
            ")",
            "",
            "# Optional: wrap back into AiiDA",
            "# from aiida.orm import StructureData",
            "# structure = StructureData(ase=atoms)",
        ]
    )
    return NodeScriptResponse(pk=pk, node_type="StructureData", language="python", script=script)


def _build_node_script_from_summary(payload: dict[str, Any]) -> NodeScriptResponse:
    node_type = str(payload.get("node_type") or payload.get("type") or "").strip()
    if node_type == "Dict":
        return _build_dict_script_from_summary(payload)
    if node_type == "StructureData":
        return _build_structure_script_from_summary(payload)
    raise HTTPException(
        status_code=422,
        detail={"error": "Copy as Script is only supported for StructureData and Dict nodes", "node_type": node_type or "Unknown"},
    )


def _fetch_context_nodes(context_node_ids: list[int]) -> list[dict[str, Any]]:
    if not context_node_ids:
        return []
    if not hub.current_profile:
        hub.start()
    return get_context_nodes(context_node_ids)


def _sanitize_upload_name(filename: str) -> str:
    safe = Path(filename).name.replace(" ", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch in {"-", "_", "."}) or "archive.aiida"


def _clear_pending_submission_memory(state: Any) -> None:
    memory = getattr(state, "memory", None)
    if memory is None:
        return
    setter = getattr(memory, "set_kv", None)
    if not callable(setter):
        return
    try:
        setter(PENDING_SUBMISSION_KEY, None)
    except Exception as error:  # noqa: BLE001
        logger.warning(log_event("aiida.frontend.pending_submission.clear_failed", error=str(error)))


def _get_frontend_groups() -> list[dict[str, Any]]:
    if not hub.current_profile:
        hub.start()
    return list_groups()


def _get_frontend_nodes(
    limit: int = 15,
    group_label: str | None = None,
    node_type: str | None = None,
    *,
    root_only: bool = True,
) -> list[dict[str, Any]]:
    if not hub.current_profile:
        hub.start()
    return get_recent_nodes(limit=limit, group_label=group_label, node_type=node_type, root_only=root_only)


def _build_active_submission_group_labels(state: Any) -> dict[str, str] | None:
    session_id = get_active_chat_session_id(state)
    if not session_id:
        return None

    session_detail = get_chat_session_detail(state, session_id)
    if not isinstance(session_detail, dict):
        return None

    project_group_label = str(session_detail.get("project_group_label") or "").strip()
    session_group_label = str(session_detail.get("session_group_label") or "").strip()
    if not project_group_label or not session_group_label:
        return None

    return {
        "project": project_group_label,
        "session": session_group_label,
    }


async def _ensure_named_groups(labels: list[str]) -> dict[str, str]:
    ensured: dict[str, str] = {}
    for raw_label in labels:
        cleaned_label = str(raw_label or "").strip()
        if not cleaned_label:
            continue
        await _ensure_submission_group(cleaned_label)
        ensured[cleaned_label] = cleaned_label
    return ensured


async def _delete_named_groups(labels: list[str]) -> dict[str, str]:
    deleted: dict[str, str] = {}
    for raw_label in labels:
        cleaned_label = str(raw_label or "").strip()
        if not cleaned_label or cleaned_label in deleted:
            continue
        existing = next((group for group in list_groups() if str(group.get("label") or "").strip() == cleaned_label), None)
        if not isinstance(existing, dict):
            continue
        try:
            delete_group(int(existing.get("pk")))
        except BridgeAPIError as exc:
            if int(exc.status_code or 0) != 404:
                raise
        deleted[cleaned_label] = cleaned_label
    return deleted


def _collect_chat_group_labels_for_deletion(
    state: Any,
    *,
    project_ids: list[str] | None = None,
    session_ids: list[str] | None = None,
) -> list[str]:
    project_id_set = {str(project_id or "").strip() for project_id in project_ids or [] if str(project_id or "").strip()}
    session_id_set = {str(session_id or "").strip() for session_id in session_ids or [] if str(session_id or "").strip()}
    if not project_id_set and not session_id_set:
        return []

    labels: list[str] = []
    seen: set[str] = set()
    sessions = list_chat_sessions(state)
    projects = list_chat_projects(state)

    for project in projects:
        if str(project.get("id") or "").strip() not in project_id_set:
            continue
        label = str(project.get("group_label") or "").strip()
        if label and label not in seen:
            seen.add(label)
            labels.append(label)

    for session in sessions:
        session_id = str(session.get("id") or "").strip()
        project_id = str(session.get("project_id") or "").strip()
        if session_id not in session_id_set and project_id not in project_id_set:
            continue
        label = str(session.get("session_group_label") or "").strip()
        if label and label not in seen:
            seen.add(label)
            labels.append(label)

    return labels


def _chat_delete_response(state: Any, deleted: dict[str, Any]) -> dict[str, Any]:
    snapshot = _chat_sessions_payload(state)
    return {
        **snapshot,
        "chat": get_chat_snapshot(state),
        "deleted_project_ids": deleted.get("deleted_project_ids") if isinstance(deleted, dict) else [],
        "deleted_session_ids": deleted.get("deleted_session_ids") if isinstance(deleted, dict) else [],
    }


def _build_submission_request_headers(state: Any) -> dict[str, str] | None:
    session_id = get_active_chat_session_id(state)
    if not session_id:
        return None

    active_project_id = get_active_chat_project_id(state)
    workspace_path = get_chat_session_workspace_path(state, session_id)
    return build_bridge_context_headers(
        session_id=session_id,
        project_id=active_project_id,
        workspace_path=workspace_path,
    )


async def _ensure_submission_group(label: str) -> dict[str, Any] | None:
    cleaned_label = str(label or "").strip()
    if not cleaned_label:
        return None

    existing = next((group for group in list_groups() if str(group.get("label") or "").strip() == cleaned_label), None)
    if existing:
        return existing

    try:
        response = create_group(cleaned_label)
    except BridgeAPIError as exc:
        if int(exc.status_code or 0) != 409:
            raise
        response = {"item": next((group for group in list_groups() if str(group.get("label") or "").strip() == cleaned_label), None)}

    group_payload = response.get("item") if isinstance(response, dict) else None
    if isinstance(group_payload, dict):
        return group_payload

    return next((group for group in list_groups() if str(group.get("label") or "").strip() == cleaned_label), None)


async def _auto_assign_submission_groups(
    state: Any,
    submitted_pks: list[int],
) -> dict[str, str] | None:
    normalized_pks = sorted({int(pk) for pk in submitted_pks if isinstance(pk, int) and pk > 0})
    if not normalized_pks:
        return None

    labels = _build_active_submission_group_labels(state)
    if not labels:
        return None

    for label in (labels["project"], labels["session"]):
        group = await _ensure_submission_group(label)
        group_pk = int(group.get("pk") or 0) if isinstance(group, dict) else 0
        if group_pk <= 0:
            continue
        add_nodes_to_group(group_pk, normalized_pks)

    return labels


def _raise_worker_http_error(exc: Exception) -> None:
    if isinstance(exc, BridgeOfflineError):
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    if isinstance(exc, BridgeAPIError):
        detail = exc.payload if isinstance(exc.payload, dict) else {"error": exc.message, "details": exc.payload}
        raise HTTPException(status_code=max(400, int(exc.status_code or 502)), detail=detail) from exc
    raise HTTPException(status_code=500, detail={"error": str(exc)}) from exc


def _normalize_model_name(name: str) -> str:
    if name.startswith("models/"):
        return name.split("/", 1)[1]
    return name


def _fetch_genai_models() -> list[str]:
    api_key = settings.GEMINI_API_KEY
    if api_key == "your-key-here":
        api_key = None

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": settings.GEMINI_API_VERSION},
    )
    discovered: list[str] = []
    for model in client.models.list():
        model_name = _normalize_model_name(getattr(model, "name", "") or "")
        if not model_name.startswith("gemini"):
            continue

        supported_actions = getattr(model, "supported_actions", None) or []
        if supported_actions and "generateContent" not in supported_actions:
            continue

        discovered.append(model_name)

    return list(dict.fromkeys(discovered))


def _get_available_models(state: Any) -> list[str]:
    cached = getattr(state, "available_models", None)
    cached_at = getattr(state, "available_models_cached_at", 0.0)
    now = time.time()

    if cached and (now - cached_at) < 900:
        return cached

    try:
        models = _fetch_genai_models()
        if not models:
            models = DEFAULT_MODELS
        elif settings.DEFAULT_MODEL in models:
            models = [settings.DEFAULT_MODEL, *[model for model in models if model != settings.DEFAULT_MODEL]]
        else:
            models = [settings.DEFAULT_MODEL, *models]
    except Exception as error:  # noqa: BLE001
        logger.warning(log_event("aiida.models.fetch.fallback", error=str(error)))
        models = DEFAULT_MODELS

    state.available_models = models
    state.available_models_cached_at = now
    return models


def _get_selected_model(state: Any, available_models: list[str]) -> str:
    selected = getattr(state, "selected_model", None)
    if selected in available_models:
        return selected
    fallback = available_models[0]
    state.selected_model = fallback
    return fallback


@router.get("/status", response_model=BridgeStatusResponse, tags=[WORKER_PROXY_TAG])
async def get_bridge_status() -> BridgeStatusResponse:
    try:
        snapshot = await bridge_service.get_status()
        return BridgeStatusResponse(
            status=snapshot.status,
            url=snapshot.url,
            environment=snapshot.environment,
            profile=snapshot.profile,
            daemon_status=snapshot.daemon_status,
            resources=SystemCountsResponse(
                computers=snapshot.resources.computers,
                codes=snapshot.resources.codes,
                workchains=snapshot.resources.workchains,
            ),
            plugins=list(snapshot.plugins),
        )
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(log_event("aiida.bridge.status.failed", error=error_message))
        return BridgeStatusResponse(
            status="offline",
            url=bridge_service.bridge_url,
            environment="Remote Bridge",
            profile="unknown",
            daemon_status=False,
            resources=SystemCountsResponse(),
            plugins=[],
        )


@router.get("/plugins", response_model=list[str], tags=[WORKER_PROXY_TAG])
async def get_bridge_plugins() -> list[str]:
    try:
        return await bridge_service.get_plugins()
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(log_event("aiida.bridge.plugins.failed", error=error_message))
        return []


@router.get("/system", response_model=BridgeSystemInfoResponse, tags=[WORKER_PROXY_TAG])
async def get_bridge_system_info() -> BridgeSystemInfoResponse:
    try:
        snapshot = await bridge_service.get_status()
        return BridgeSystemInfoResponse(
            profile=snapshot.profile,
            counts=SystemCountsResponse(
                computers=snapshot.resources.computers,
                codes=snapshot.resources.codes,
                workchains=snapshot.resources.workchains,
            ),
            daemon_status=snapshot.daemon_status,
        )
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(log_event("aiida.bridge.system.failed", error=error_message))
        return BridgeSystemInfoResponse()


@router.get("/resources", response_model=BridgeResourcesResponse, tags=[WORKER_PROXY_TAG])
async def get_bridge_resources() -> BridgeResourcesResponse:
    try:
        payload = await bridge_service.get_resources()
        return BridgeResourcesResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(log_event("aiida.bridge.resources.failed", error=error_message))
        return BridgeResourcesResponse()


@router.get("/profiles", response_model=BridgeProfilesResponse, tags=[WORKER_PROXY_TAG])
async def get_bridge_profiles() -> BridgeProfilesResponse:
    try:
        payload = await bridge_service.get_profiles()
        return BridgeProfilesResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(log_event("aiida.bridge.profiles.failed", error=error_message))
        return BridgeProfilesResponse()


@router.post("/profiles/switch", response_model=BridgeSwitchProfileResponse, tags=[WORKER_PROXY_TAG])
async def switch_bridge_profile(payload: BridgeSwitchProfileRequest) -> BridgeSwitchProfileResponse:
    try:
        raw = await bridge_service.switch_profile(payload.profile)
        return BridgeSwitchProfileResponse.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        logger.warning(log_event("aiida.bridge.profile_switch.failed", error=error_message))
        return BridgeSwitchProfileResponse(status="error", current_profile=None)


@router.get("/management/infrastructure", response_model=list[InfrastructureComputer], tags=[WORKER_PROXY_TAG])
async def get_management_infrastructure():
    """Proxy to fetch hierarchical infrastructure (Computers -> Codes)."""
    try:
        return await bridge_service.inspect_infrastructure_v2()
    except Exception as exc:
        _raise_worker_http_error(exc)


@router.post("/management/infrastructure/setup", tags=[WORKER_PROXY_TAG])
async def setup_management_infrastructure(payload: dict[str, Any]):
    """Proxy to setup a new computer, authentication, and code."""
    try:
        return await bridge_service.setup_infrastructure(payload)
    except Exception as exc:
        _raise_worker_http_error(exc)


@router.get(
    "/management/infrastructure/computer/pk/{computer_pk}/export",
    response_model=InfrastructureExportResponse,
    tags=[WORKER_PROXY_TAG],
)
async def export_management_computer(computer_pk: int = ApiPath(..., ge=1)):
    try:
        payload = await request_json("GET", f"/management/infrastructure/computer/pk/{int(computer_pk)}/export")
    except Exception as exc:
        _raise_worker_http_error(exc)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail={"error": "Worker returned an invalid computer export payload"})
    return InfrastructureExportResponse(**payload)


@router.get(
    "/management/infrastructure/code/{code_pk}/export",
    response_model=InfrastructureExportResponse,
    tags=[WORKER_PROXY_TAG],
)
async def export_management_code(code_pk: int = ApiPath(..., ge=1)):
    try:
        payload = await request_json("GET", f"/management/infrastructure/code/{int(code_pk)}/export")
    except Exception as exc:
        _raise_worker_http_error(exc)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail={"error": "Worker returned an invalid code export payload"})
    return InfrastructureExportResponse(**payload)


@router.get("/management/profiles/current-user-info", response_model=UserInfoResponse, tags=[WORKER_PROXY_TAG])
async def get_current_user_info():
    """Proxy to fetch current user information from the worker."""
    try:
        return await bridge_service.get_current_user_info()
    except Exception as exc:
        _raise_worker_http_error(exc)


@router.post("/management/profiles/setup", tags=[WORKER_PROXY_TAG])
async def setup_profile(payload: ProfileSetupRequest):
    """Proxy to setup a new AiiDA profile on the worker."""
    try:
        return await bridge_service.setup_profile(payload.model_dump())
    except Exception as exc:
        _raise_worker_http_error(exc)


async def _submit_bridge_workchain_impl(
    request: Request,
    payload: SubmissionDraftRequest,
    *,
    require_batch_list: bool = False,
):
    if not payload.draft:
        raise HTTPException(status_code=422, detail="Submission draft is required")

    draft_payload = payload.draft
    if require_batch_list and not isinstance(draft_payload, list):
        raise HTTPException(status_code=422, detail="Batch submission draft list is required")
    worker_request_headers = _build_submission_request_headers(request.app.state)
    if isinstance(draft_payload, list):
        if len(draft_payload) == 0:
            raise HTTPException(status_code=422, detail="Submission draft list cannot be empty")
        try:
            raw = await request_json(
                "POST",
                "/submission/submit",
                json={"draft": draft_payload},
                headers=worker_request_headers,
            )
        except Exception as exc:
            _raise_worker_http_error(exc)

        batch_response = format_worker_batch_submission_response(raw)
        submitted_pks = [
            int(pk)
            for pk in batch_response.get("submitted_pks", [])
            if isinstance(pk, int) and pk > 0
        ]
        if submitted_pks:
            _clear_pending_submission_memory(request.app.state)
        try:
            auto_groups = await _auto_assign_submission_groups(request.app.state, submitted_pks)
        except Exception as exc:  # noqa: BLE001
            logger.warning(log_event("aiida.frontend.submission.auto_group_failed", error=str(exc), submitted_pks=submitted_pks))
        else:
            if auto_groups:
                batch_response["auto_groups"] = auto_groups
        return batch_response

    try:
        raw = await request_json(
            "POST",
            "/submission/submit",
            json={"draft": draft_payload},
            headers=worker_request_headers,
        )
        response = format_single_submission_response(raw)
        _clear_pending_submission_memory(request.app.state)
        try:
            auto_groups = await _auto_assign_submission_groups(request.app.state, response.get("submitted_pks", []))
        except Exception as exc:  # noqa: BLE001
            logger.warning(log_event("aiida.frontend.submission.auto_group_failed", error=str(exc), response=response))
        else:
            if auto_groups:
                response["auto_groups"] = auto_groups
        return response
    except BridgeOfflineError as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    except BridgeAPIError as exc:
        detail = exc.payload if isinstance(exc.payload, dict) else {"error": exc.message, "details": exc.payload}
        raise HTTPException(status_code=max(400, int(exc.status_code or 502)), detail=detail) from exc


@router.post("/submission/submit", tags=[WORKER_PROXY_TAG])
async def submit_bridge_workchain(request: Request, payload: SubmissionDraftRequest):
    return await _submit_bridge_workchain_impl(request, payload)


@router.post("/submission/submit_batch", tags=[WORKER_PROXY_TAG])
async def submit_bridge_workchain_batch(request: Request, payload: SubmissionDraftRequest):
    return await _submit_bridge_workchain_impl(request, payload, require_batch_list=True)


@router.get("/process/events", tags=[WORKER_PROXY_TAG])
async def worker_process_events(request: Request):
    """Proxy SSE stream of real-time process state changes from the worker."""
    worker_url = bridge_endpoint("/process/events")

    async def _proxy_generator():
        try:
            async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
                async with client.stream("GET", worker_url) as response:
                    if response.status_code != 200:
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": f"Worker returned {response.status_code}"}),
                        }
                        return
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        while "\n\n" in buffer:
                            raw_event, buffer = buffer.split("\n\n", 1)
                            lines = raw_event.strip().split("\n")
                            event_name = "message"
                            data_lines = []
                            for line in lines:
                                if line.startswith("event:"):
                                    event_name = line[6:].strip()
                                elif line.startswith("data:"):
                                    data_lines.append(line[5:].strip())
                                elif line.startswith(":"):
                                    continue  # comment / keepalive
                            if data_lines:
                                yield {"event": event_name, "data": "\n".join(data_lines)}
        except httpx.ConnectError:
            yield {
                "event": "error",
                "data": json.dumps({"error": "AiiDA Worker is offline"}),
            }
        except Exception as exc:
            logger.warning(log_event("aiida.process_events.proxy.failed", error=str(exc)))
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}),
            }

    return EventSourceResponse(_proxy_generator())


@router.get("/data/remote/{pk}/files", tags=[WORKER_PROXY_TAG])
async def worker_remote_files(pk: int):
    try:
        return await request_json("GET", f"/data/remote/{int(pk)}/files")
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)


@router.get("/data/bands/{pk}", tags=[WORKER_PROXY_TAG])
async def worker_bands_data(pk: int):
    try:
        return await request_json("GET", f"/data/bands/{int(pk)}")
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)


@router.get("/data/remote/{pk}/files/{filename:path}", tags=[WORKER_PROXY_TAG])
async def worker_remote_file_content(pk: int, filename: str):
    try:
        return await request_json("GET", f"/data/remote/{int(pk)}/files/{filename}")
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)


@router.get("/data/repository/{pk}/files", tags=[WORKER_PROXY_TAG])
async def worker_repository_files(
    pk: int,
    source: str = Query(default="folder"),
):
    try:
        return await request_json(
            "GET",
            f"/data/repository/{int(pk)}/files",
            params={"source": source},
        )
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)


@router.get("/data/repository/{pk}/files/{filename:path}", tags=[WORKER_PROXY_TAG])
async def worker_repository_file_content(
    pk: int,
    filename: str,
    source: str = Query(default="folder"),
):
    try:
        return await request_json(
            "GET",
            f"/data/repository/{int(pk)}/files/{filename}",
            params={"source": source},
        )
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)


@router.get("/process/{identifier}", tags=[WORKER_PROXY_TAG])
async def worker_process_detail(identifier: str):
    try:
        payload = await request_json("GET", f"/process/{identifier}")
        if isinstance(payload, dict):
            return await _enrich_process_detail_payload(payload)
        return {"data": payload}
    except BridgeOfflineError as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    except BridgeAPIError as exc:
        detail = exc.payload if isinstance(exc.payload, dict) else {"error": exc.message, "details": exc.payload}
        raise HTTPException(status_code=max(400, int(exc.status_code or 502)), detail=detail) from exc


@router.get("/process/{identifier}/logs", tags=[WORKER_PROXY_TAG])
async def worker_process_logs(identifier: str):
    try:
        payload = await request_json("GET", f"/process/{identifier}/logs")
        return payload if isinstance(payload, dict) else {"data": payload}
    except BridgeOfflineError as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    except BridgeAPIError as exc:
        detail = exc.payload if isinstance(exc.payload, dict) else {"error": exc.message, "details": exc.payload}
        raise HTTPException(status_code=max(400, int(exc.status_code or 502)), detail=detail) from exc


@router.post("/data/import/{data_type}", tags=[WORKER_PROXY_TAG])
async def proxy_import_data(
    data_type: str,
    source_type: str = Form(...),
    label: str | None = Form(None),
    description: str | None = Form(None),
    raw_text: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    """Proxy data import to aiida-worker."""
    files = {}
    if file:
        file_content = await file.read()
        files = {"file": (file.filename, file_content, file.content_type)}

    data = {
        "source_type": source_type,
        "label": label,
        "description": description,
        "raw_text": raw_text,
    }
    # Filter out None values
    data = {k: v for k, v in data.items() if v is not None}

    try:
        return await bridge_service.request_multipart(
            "POST",
            f"/data/import/{data_type}",
            files=files,
            data=data,
        )
    except Exception as exc:
        _raise_worker_http_error(exc)


@router.get("/frontend/bootstrap", tags=[FRONTEND_TAG])
async def frontend_bootstrap(request: Request):
    state = request.app.state
    try:
        processes = _get_frontend_nodes(limit=15)
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.bootstrap.processes.failed", error=str(error)))
        processes = []

    try:
        groups = _get_frontend_groups()
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.bootstrap.groups.failed", error=str(error)))
        groups = []

    available_models = _get_available_models(state)
    selected_model = _get_selected_model(state, available_models)
    log_version, log_lines = get_log_buffer_snapshot(limit=240)
    chat_snapshot = get_chat_snapshot(state)

    return {
        "processes": _serialize_processes(processes),
        "groups": _serialize_groups(groups),
        "chat": chat_snapshot,
        "logs": {
            "version": log_version,
            "lines": log_lines[-160:],
        },
        "models": available_models,
        "selected_model": selected_model,
        "quick_prompts": _get_quick_prompts(),
    }


@router.get("/frontend/specializations/active", tags=[FRONTEND_TAG])
async def frontend_active_specializations(
    context_node_ids: list[int] | None = Query(default=None),
    project_tags: list[str] | None = Query(default=None),
    resource_plugins: list[str] | None = Query(default=None),
    selected_environment: str | None = Query(default=None),
    auto_switch: bool = Query(default=True),
):
    return await build_active_specializations_payload(
        context_node_ids=context_node_ids,
        project_tags=_normalize_text_query_values(project_tags),
        resource_plugins=_normalize_text_query_values(resource_plugins),
        selected_environment=selected_environment,
        auto_switch=auto_switch,
    )


@router.get("/frontend/groups", tags=[FRONTEND_TAG])
async def frontend_groups():
    try:
        items = _get_frontend_groups()
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.groups.failed", error=str(error)))
        items = []
    return {"items": _serialize_groups(items)}


@router.post("/frontend/groups/create", tags=[FRONTEND_TAG])
async def frontend_create_group(payload: FrontendGroupCreateRequest):
    if not hub.current_profile:
        hub.start()
    try:
        response = create_group(payload.label)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    return {"item": _serialize_groups([response])[0] if isinstance(response, dict) else None}


@router.put("/frontend/groups/{pk}/label", tags=[FRONTEND_TAG])
async def frontend_rename_group(pk: int, payload: FrontendGroupRenameRequest):
    if not hub.current_profile:
        hub.start()
    try:
        response = rename_group(pk, payload.label)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    return {"item": _serialize_groups([response])[0] if isinstance(response, dict) else None}


@router.delete("/frontend/groups/{pk}", tags=[FRONTEND_TAG])
async def frontend_delete_group(pk: int):
    if not hub.current_profile:
        hub.start()
    try:
        response = delete_group(pk)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    return response if isinstance(response, dict) else {"status": "deleted", "pk": int(pk)}


@router.post("/frontend/groups/{pk}/nodes", tags=[FRONTEND_TAG])
async def frontend_add_nodes_to_group(pk: int, payload: FrontendGroupAssignNodesRequest):
    if not hub.current_profile:
        hub.start()
    try:
        response = add_nodes_to_group(pk, payload.node_pks)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    if not isinstance(response, dict):
        return {"group": None, "added": [], "missing": []}
    group_payload = response.get("group")
    response_payload = dict(response)
    response_payload["group"] = _serialize_groups([group_payload])[0] if isinstance(group_payload, dict) else None
    return response_payload


@router.get("/frontend/groups/{pk}/export", tags=[FRONTEND_TAG])
async def frontend_export_group(pk: int):
    if not hub.current_profile:
        hub.start()
    try:
        response = export_group_archive(pk)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    headers: dict[str, str] = {}
    content_disposition = response.headers.get("content-disposition")
    if isinstance(content_disposition, str) and content_disposition.strip():
        headers["Content-Disposition"] = content_disposition
    return Response(
        content=response.content,
        media_type=response.media_type or "application/octet-stream",
        headers=headers,
    )


@router.post("/frontend/archives/upload", tags=[FRONTEND_TAG])
async def frontend_upload_archive(file: UploadFile = File(...)):
    filename = file.filename or "archive.aiida"
    extension = Path(filename).suffix.lower()
    if extension not in ARCHIVE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported archive format")

    upload_root = Path(tempfile.gettempdir()) / "aris-aiida-uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    target_name = f"{int(time.time() * 1000)}-{_sanitize_upload_name(filename)}"
    target_path = upload_root / target_name

    payload = await file.read()
    target_path.write_bytes(payload)
    await file.close()

    profile_name = hub.import_archive(target_path)
    return {
        "status": "uploaded",
        "profile_name": profile_name,
        "stored_path": str(target_path),
    }


@router.get("/frontend/processes", tags=[FRONTEND_TAG])
async def frontend_processes(
    limit: int = Query(default=15, ge=1, le=100),
    group_label: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
    root_only: bool = Query(default=True),
):
    try:
        processes = _get_frontend_nodes(limit=limit, group_label=group_label, node_type=node_type, root_only=root_only)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.processes.failed", error=str(error)))
        processes = []
    return {"items": _serialize_processes(processes)}


@router.get("/frontend/processes/{identifier}/clone-draft", tags=[FRONTEND_TAG])
async def frontend_clone_process_draft(identifier: str):
    try:
        payload = await request_json("GET", f"/process/{identifier}/clone-draft")
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail={"error": "Worker returned an invalid clone draft payload"})

    try:
        return enrich_submission_draft_payload(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            log_event(
                "aiida.frontend.clone_draft.enrich_failed",
                identifier=str(identifier),
                error=str(exc),
            )
        )
        raise HTTPException(status_code=500, detail={"error": "Failed to prepare clone draft", "reason": str(exc)}) from exc


@router.get("/frontend/ssh-hosts", tags=[FRONTEND_TAG])
async def frontend_ssh_hosts():
    try:
        hosts = await bridge_service.get_ssh_config()
        return {"items": hosts}
    except Exception as error:
        logger.exception(log_event("aiida.frontend.ssh_hosts.failed", error=str(error)))
        raise HTTPException(status_code=500, detail="Failed to fetch SSH hosts")

@router.post("/frontend/infrastructure/setup-code", tags=[FRONTEND_TAG])
async def frontend_setup_code(payload: CodeSetupRequest):
    """Proxy code setup to AIIDA worker."""
    logger.info(log_event("aiida.frontend.setup_code.request", computer=payload.computer_label, label=payload.label))
    try:
        response = await bridge_service.setup_code(payload)
        logger.info(log_event("aiida.frontend.setup_code.success", pk=response.get("pk")))
        return response
    except Exception as exc:
        logger.error(log_event("aiida.frontend.setup_code.failed", error=str(exc)))
        _raise_worker_http_error(exc)

@router.get("/frontend/infrastructure/computer/{computer_label}/codes", response_model=list[CodeDetailedResponse], tags=[FRONTEND_TAG])
async def frontend_get_computer_codes(computer_label: str):
    """Proxy fetching detailed computer codes to AIIDA worker."""
    try:
        response = await bridge_service.get_computer_codes(computer_label)
        return response
    except Exception as exc:
        _raise_worker_http_error(exc)


@router.post("/frontend/parse-infrastructure", tags=[FRONTEND_TAG])
async def parse_infrastructure_via_ai(payload: ParseInfrastructureRequest):
    """Proxy to AiiDA service for AI infrastructure parsing."""
    try:
        parsed = await _parse_infrastructure_via_ai(payload.text, payload.ssh_host_details)
        return {"status": "success", "data": parsed}
    except Exception as error:
        logger.exception(log_event("aiida.frontend.parse_infrastructure.failed", error=str(error)))
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"AI Parsing failed: {str(error)}")


@router.get(
    "/frontend/nodes/{pk}/metadata",
    response_model=NodeHoverMetadataResponse,
    tags=[FRONTEND_TAG],
)
async def frontend_node_hover_metadata(pk: int = ApiPath(..., ge=1)) -> NodeHoverMetadataResponse:
    return _get_node_hover_metadata(pk)


@router.get(
    "/frontend/nodes/{pk}/script",
    response_model=NodeScriptResponse,
    tags=[FRONTEND_TAG],
)
async def frontend_node_script(pk: int = ApiPath(..., ge=1)) -> NodeScriptResponse:
    try:
        payload = await request_json("GET", f"/management/nodes/{pk}/script")
    except BridgeAPIError as exc:
        if int(exc.status_code or 0) != 404:
            _raise_worker_http_error(exc)
        try:
            summary_payload = await request_json("GET", f"/management/nodes/{pk}")
        except Exception as fallback_exc:  # noqa: BLE001
            _raise_worker_http_error(fallback_exc)
        if not isinstance(summary_payload, dict):
            raise HTTPException(status_code=502, detail={"error": "Worker returned an invalid node summary payload"})
        return _build_node_script_from_summary(summary_payload)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail={"error": "Worker returned an invalid node script payload"})
    return NodeScriptResponse(**payload)


@router.post("/frontend/nodes/{pk}/soft-delete", tags=[FRONTEND_TAG])
async def frontend_node_soft_delete(
    pk: int = ApiPath(..., ge=1),
    payload: FrontendNodeSoftDeleteRequest | None = None,
):
    if not hub.current_profile:
        hub.start()
    deleted = bool(payload.deleted) if isinstance(payload, FrontendNodeSoftDeleteRequest) else True
    try:
        response = soft_delete_node(pk, deleted=deleted)
    except Exception as exc:  # noqa: BLE001
        _raise_worker_http_error(exc)
    return response if isinstance(response, dict) else {"pk": int(pk), "soft_deleted": deleted}


@router.get("/frontend/processes/stream", tags=[FRONTEND_TAG])
async def frontend_processes_stream(
    request: Request,
    limit: int = Query(default=15, ge=1, le=100),
    group_label: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
):
    try:
        _get_frontend_nodes(limit=1, group_label=group_label, node_type=node_type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    async def event_generator():
        stream_id = id(request)
        last_digest = ""
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.process_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.process_stream.disconnected", stream_id=stream_id))
                break

            try:
                processes = _serialize_processes(
                    _get_frontend_nodes(limit=limit, group_label=group_label, node_type=node_type)
                )
                digest = hashlib.sha1(json.dumps(processes, sort_keys=True).encode("utf-8")).hexdigest()
                now = time.monotonic()
                should_push = (digest != last_digest) or ((now - heartbeat_ts) >= 15)
                if should_push:
                    yield {"event": "processes", "data": json.dumps({"items": processes})}
                    last_digest = digest
                    heartbeat_ts = now
            except Exception as error:  # noqa: BLE001
                logger.exception(
                    log_event("aiida.frontend.process_stream.failed", stream_id=stream_id, error=str(error))
                )
                yield {"event": "processes", "data": json.dumps({"items": []})}

            await asyncio.sleep(1.5)

    return EventSourceResponse(event_generator())


@router.get("/frontend/logs", tags=[FRONTEND_TAG])
async def frontend_logs(limit: int = Query(default=240, ge=20, le=1000)):
    version, lines = get_log_buffer_snapshot(limit=limit)
    return {"version": version, "lines": lines}


@router.get("/frontend/logs/stream", tags=[FRONTEND_TAG])
async def frontend_logs_stream(request: Request, limit: int = Query(default=240, ge=20, le=1000)):
    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.log_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.log_stream.disconnected", stream_id=stream_id))
                break

            try:
                version, lines = get_log_buffer_snapshot(limit=limit)
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 8.0)
                if should_push:
                    yield {"event": "logs", "data": json.dumps({"version": version, "lines": lines})}
                    last_version = version
                    heartbeat_ts = now
            except Exception as error:  # noqa: BLE001
                logger.exception(
                    log_event("aiida.frontend.log_stream.failed", stream_id=stream_id, error=str(error))
                )
                yield {"event": "logs", "data": json.dumps({"version": -1, "lines": []})}

            await asyncio.sleep(0.75)

    return EventSourceResponse(event_generator())


@router.post("/frontend/submission/pending/cancel", tags=[FRONTEND_TAG])
async def frontend_cancel_pending_submission(request: Request):
    _clear_pending_submission_memory(request.app.state)
    return {"status": "cancelled"}


@router.get("/frontend/chat/messages", tags=[FRONTEND_TAG])
async def frontend_chat_messages(request: Request):
    state = request.app.state
    return get_chat_snapshot(state)


@router.get("/frontend/chat/sessions", tags=[FRONTEND_TAG])
async def frontend_chat_sessions(request: Request):
    state = request.app.state
    return _chat_sessions_payload(state)


@router.get("/frontend/chat/sessions/{session_id}/batch-progress", tags=[FRONTEND_TAG])
async def frontend_chat_session_batch_progress(request: Request, session_id: str):
    state = request.app.state
    if get_chat_session_detail(state, session_id) is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"item": get_chat_session_batch_progress(state, session_id)}


@router.get("/frontend/chat/projects", tags=[FRONTEND_TAG])
async def frontend_chat_projects(request: Request):
    state = request.app.state
    return {
        "active_project_id": get_active_chat_project_id(state),
        "items": list_chat_projects(state),
    }


@router.post("/frontend/chat/projects", tags=[FRONTEND_TAG])
async def frontend_create_chat_project(request: Request, payload: FrontendChatProjectCreateRequest):
    state = request.app.state
    try:
        project = create_chat_project(
            state,
            name=payload.name,
            root_path=payload.root_path,
            activate=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    project_group_label = str(project.get("group_label") or "").strip()
    if project_group_label:
        try:
            await _ensure_named_groups([project_group_label])
        except Exception as exc:  # noqa: BLE001
            logger.warning(log_event("aiida.frontend.project_group.ensure_failed", error=str(exc), label=project_group_label))
    return {
        "project": project,
        "active_project_id": get_active_chat_project_id(state),
        "projects": list_chat_projects(state),
    }


@router.post("/frontend/chat/sessions", tags=[FRONTEND_TAG])
async def frontend_create_chat_session(request: Request, payload: FrontendChatSessionCreateRequest):
    state = request.app.state
    session = create_chat_session(
        state,
        title=payload.title,
        snapshot=payload.snapshot if isinstance(payload.snapshot, dict) else None,
        activate=True,
        archive_session_id=payload.archive_session_id,
        project_id=payload.project_id,
    )
    labels = [
        str(session.get("project_group_label") or "").strip(),
        str(session.get("session_group_label") or "").strip(),
    ]
    try:
        await _ensure_named_groups(labels)
    except Exception as exc:  # noqa: BLE001
        logger.warning(log_event("aiida.frontend.session_groups.ensure_failed", error=str(exc), labels=labels))
    return {
        "session": session,
        "chat": get_chat_snapshot(state),
        "active_session_id": get_active_chat_session_id(state),
        "active_project_id": get_active_chat_project_id(state),
        "projects": list_chat_projects(state),
        "version": int(getattr(state, "chat_sessions_version", 0)),
    }


@router.delete("/frontend/chat/projects/{project_id}", tags=[FRONTEND_TAG])
async def frontend_delete_chat_project(request: Request, project_id: str):
    state = request.app.state
    labels = _collect_chat_group_labels_for_deletion(state, project_ids=[project_id])
    deleted = delete_chat_items(state, project_ids=[project_id])
    if project_id not in set(deleted.get("deleted_project_ids") or []):
        raise HTTPException(status_code=404, detail="Chat project not found")
    try:
        await _delete_named_groups(labels)
    except Exception as exc:  # noqa: BLE001
        logger.warning(log_event("aiida.frontend.project_groups.delete_failed", error=str(exc), labels=labels))
    return _chat_delete_response(state, deleted)


@router.delete("/frontend/chat/sessions/{session_id}", tags=[FRONTEND_TAG])
async def frontend_delete_chat_session(request: Request, session_id: str):
    state = request.app.state
    labels = _collect_chat_group_labels_for_deletion(state, session_ids=[session_id])
    deleted = delete_chat_items(state, session_ids=[session_id])
    if session_id not in set(deleted.get("deleted_session_ids") or []):
        raise HTTPException(status_code=404, detail="Chat session not found")
    try:
        await _delete_named_groups(labels)
    except Exception as exc:  # noqa: BLE001
        logger.warning(log_event("aiida.frontend.session_groups.delete_failed", error=str(exc), labels=labels))
    return _chat_delete_response(state, deleted)


@router.post("/frontend/chat/delete", tags=[FRONTEND_TAG])
async def frontend_delete_chat_items(request: Request, payload: FrontendChatDeleteRequest):
    state = request.app.state
    project_ids = [str(value or "").strip() for value in payload.project_ids if str(value or "").strip()]
    session_ids = [str(value or "").strip() for value in payload.session_ids if str(value or "").strip()]
    if not project_ids and not session_ids:
        raise HTTPException(status_code=400, detail={"error": "No project_ids or session_ids provided"})

    labels = _collect_chat_group_labels_for_deletion(
        state,
        project_ids=project_ids,
        session_ids=session_ids,
    )
    deleted = delete_chat_items(state, project_ids=project_ids, session_ids=session_ids)
    if not (deleted.get("deleted_project_ids") or deleted.get("deleted_session_ids")):
        raise HTTPException(status_code=404, detail="No matching chat items found")
    try:
        await _delete_named_groups(labels)
    except Exception as exc:  # noqa: BLE001
        logger.warning(log_event("aiida.frontend.chat_groups.bulk_delete_failed", error=str(exc), labels=labels))
    return _chat_delete_response(state, deleted)


@router.post("/frontend/chat/sessions/{session_id}/activate", tags=[FRONTEND_TAG])
async def frontend_activate_chat_session(request: Request, session_id: str):
    state = request.app.state
    session = activate_chat_session(state, session_id)
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


@router.patch("/frontend/chat/sessions/{session_id}", tags=[FRONTEND_TAG])
async def frontend_update_chat_session(
    request: Request,
    session_id: str,
    payload: FrontendChatSessionUpdateRequest,
):
    state = request.app.state
    update_kwargs: dict[str, Any] = {}
    if "title" in payload.model_fields_set:
        update_kwargs["title"] = payload.title
    if "tags" in payload.model_fields_set:
        update_kwargs["tags"] = payload.tags
    if "snapshot" in payload.model_fields_set:
        update_kwargs["snapshot"] = payload.snapshot
    session = update_chat_session(state, session_id, **update_kwargs)
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


@router.put("/frontend/chat/sessions/{session_id}/title", tags=[FRONTEND_TAG])
async def frontend_update_chat_session_title(
    request: Request,
    session_id: str,
    payload: FrontendChatSessionTitleUpdateRequest,
):
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


@router.get("/frontend/chat/sessions/{session_id}/workspace", tags=[FRONTEND_TAG])
async def frontend_chat_session_workspace(
    request: Request,
    session_id: str,
    relative_path: str | None = Query(default=None),
):
    state = request.app.state
    try:
        payload = list_chat_session_workspace_files(state, session_id, relative_path=relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return payload


@router.get("/frontend/chat/projects/{project_id}/workspace", tags=[FRONTEND_TAG])
async def frontend_chat_project_workspace(
    request: Request,
    project_id: str,
    relative_path: str | None = Query(default=None),
):
    state = request.app.state
    try:
        payload = list_chat_project_workspace_files(state, project_id, relative_path=relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="Chat project not found")
    return payload


@router.get("/frontend/chat/stream", tags=[FRONTEND_TAG])
async def frontend_chat_stream(request: Request):
    state = request.app.state

    async def event_generator():
        stream_id = id(request)
        last_chat_version = -1
        last_sessions_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.chat_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.chat_stream.disconnected", stream_id=stream_id))
                break

            try:
                chat_version = int(getattr(state, "chat_version", 0))
                sessions_version = int(getattr(state, "chat_sessions_version", 0))
                chat_snapshot = get_chat_snapshot(state)
                sessions_snapshot = _chat_sessions_payload(state)
                now = time.monotonic()
                should_push_heartbeat = (now - heartbeat_ts) >= 10
                pushed = False
                if chat_version != last_chat_version or should_push_heartbeat:
                    yield {
                        "event": "chat",
                        "data": json.dumps(chat_snapshot),
                    }
                    last_chat_version = chat_version
                    pushed = True
                if sessions_version != last_sessions_version or should_push_heartbeat:
                    yield {
                        "event": "sessions",
                        "data": json.dumps(sessions_snapshot),
                    }
                    last_sessions_version = sessions_version
                    pushed = True
                if pushed:
                    heartbeat_ts = now
            except Exception as error:  # noqa: BLE001
                logger.exception(
                    log_event("aiida.frontend.chat_stream.failed", stream_id=stream_id, error=str(error))
                )
                yield {
                    "event": "chat",
                    "data": json.dumps({"version": -1, "session_id": None, "messages": [], "snapshot": {}}),
                }
                yield {
                    "event": "sessions",
                    "data": json.dumps({"version": -1, "active_session_id": None, "active_project_id": None, "projects": [], "items": []}),
                }

            await asyncio.sleep(0.4)

    return EventSourceResponse(event_generator())


@router.post("/frontend/chat", tags=[FRONTEND_TAG])
async def frontend_chat_submit(request: Request, payload: FrontendChatRequest):
    state = request.app.state
    user_intent = payload.intent.strip()
    if not user_intent:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    available_models = _get_available_models(state)
    selected_model = (
        payload.model_name
        if payload.model_name and payload.model_name in available_models
        else _get_selected_model(state, available_models)
    )
    state.selected_model = selected_model
    metadata = _coerce_chat_metadata(payload.metadata)
    context_node_ids = normalize_context_node_ids(
        [*(payload.context_node_ids or []), *(payload.context_pks or [])]
    )
    if context_node_ids:
        metadata["context_pks"] = context_node_ids
        metadata["context_node_pks"] = context_node_ids

    turn_id = start_chat_turn(
        state,
        user_intent=user_intent,
        selected_model=selected_model,
        fetch_context_nodes=_fetch_context_nodes,
        context_archive=payload.context_archive,
        context_node_ids=context_node_ids,
        metadata=metadata,
        source="frontend",
    )
    return {
        "status": "queued",
        "turn_id": turn_id,
        "selected_model": selected_model,
        "version": int(getattr(state, "chat_version", 0)),
    }


@router.post("/frontend/chat/stop", tags=[FRONTEND_TAG])
async def frontend_chat_stop(request: Request, payload: FrontendStopChatRequest):
    state = request.app.state
    cancelled_turn_id = cancel_chat_turn(state, payload.turn_id)
    return {
        "status": "stopped" if cancelled_turn_id is not None else "idle",
        "turn_id": cancelled_turn_id,
        "version": int(getattr(state, "chat_version", 0)),
    }
