from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Path as ApiPath, Query, Request, UploadFile
from google import genai
from loguru import logger
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.sab_core.config import settings
from src.sab_core.logging_utils import get_log_buffer_snapshot, log_event

from .chat import (
    cancel_chat_turn,
    get_chat_history,
    normalize_context_node_ids,
    serialize_chat_history,
    start_chat_turn,
)
from .client import BridgeAPIError, BridgeOfflineError, bridge_service, request_json
from .presenters.node_view import (
    attach_tree_links as _attach_tree_links,
    enrich_process_detail_payload as _enrich_process_detail_payload,
    extract_folder_preview as _extract_folder_preview,
    serialize_group_labels as _serialize_group_labels,
    serialize_processes as _serialize_processes,
)
from .presenters.workflow_view import (
    extract_submitted_pk as _extract_submitted_pk,
    format_batch_submission_response,
    format_single_submission_response,
)
from .service import (
    get_context_nodes,
    get_recent_nodes,
    list_group_labels,
    hub,
)

FRONTEND_TAG = "AiiDA-Frontend-API"
WORKER_PROXY_TAG = "AiiDA-Worker-Proxy"

router = APIRouter()
DEFAULT_MODELS = [settings.DEFAULT_MODEL]
QUICK_PROMPTS: list[tuple[str, str]] = [
    ("structure relaxation", "perform vc-relax using PseudoDojo"),
    ("band structure", "calculate the electron band structure using PseudoDojo"),
    (
        "relax+band",
        "perform vc-relax and then use the optimized structure to calculate the electron band structure",
    ),
    ("check pseudopotential", "check the PseudoDojo library in the database"),
]
ARCHIVE_EXTENSIONS = {".aiida", ".zip"}
PENDING_SUBMISSION_KEY = "aiida_pending_submission"


class FrontendChatRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=12000)
    model_name: str | None = None
    context_archive: str | None = None
    context_node_ids: list[int] | None = None
    context_pks: list[int] | None = None
    metadata: dict[str, Any] | None = None


class FrontendStopChatRequest(BaseModel):
    turn_id: int | None = None


class SubmissionDraftRequest(BaseModel):
    draft: dict[str, Any] | list[dict[str, Any]] = Field(default_factory=dict)


class SystemCountsResponse(BaseModel):
    computers: int = 0
    codes: int = 0
    workchains: int = 0


class BridgeStatusResponse(BaseModel):
    status: Literal["online", "offline"]
    url: str
    environment: str
    profile: str = "unknown"
    daemon_status: bool = False
    resources: SystemCountsResponse = Field(default_factory=SystemCountsResponse)
    plugins: list[str] = Field(default_factory=list)


class BridgeSystemInfoResponse(BaseModel):
    profile: str = "unknown"
    counts: SystemCountsResponse = Field(default_factory=SystemCountsResponse)
    daemon_status: bool = False


class ComputerResourceResponse(BaseModel):
    label: str
    hostname: str
    description: str | None = None


class CodeResourceResponse(BaseModel):
    label: str
    default_plugin: str | None = None
    computer_label: str | None = None


class BridgeResourcesResponse(BaseModel):
    computers: list[ComputerResourceResponse] = Field(default_factory=list)
    codes: list[CodeResourceResponse] = Field(default_factory=list)


class BridgeProfileResponse(BaseModel):
    name: str
    is_default: bool = False
    is_active: bool = False


class BridgeProfilesResponse(BaseModel):
    current_profile: str | None = None
    default_profile: str | None = None
    profiles: list[BridgeProfileResponse] = Field(default_factory=list)


class BridgeSwitchProfileRequest(BaseModel):
    profile: str = Field(..., min_length=1)


class BridgeSwitchProfileResponse(BaseModel):
    status: str = "switched"
    current_profile: str | None = None


class NodeHoverMetadataResponse(BaseModel):
    pk: int
    formula: str | None = None
    spacegroup: str | None = None
    node_type: str = "Unknown"


def _coerce_chat_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    metadata: dict[str, Any] = {}
    for key, value in raw.items():
        cleaned_key = str(key).strip()
        if not cleaned_key:
            continue
        metadata[cleaned_key] = value
    return metadata


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _find_first_named_value(payload: Any, candidate_keys: set[str], depth: int = 0) -> Any:
    if depth > 8:
        return None

    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).strip().lower()
            if lowered in candidate_keys and not _is_empty_value(value):
                return value
            nested = _find_first_named_value(value, candidate_keys, depth + 1)
            if nested is not None:
                return nested
        return None

    if isinstance(payload, (list, tuple, set)):
        for entry in payload:
            nested = _find_first_named_value(entry, candidate_keys, depth + 1)
            if nested is not None:
                return nested

    return None


def _format_spacegroup_value(value: Any) -> str | None:
    if isinstance(value, dict):
        symbol = _coerce_text(
            value.get("symbol")
            or value.get("international_short")
            or value.get("international_symbol")
            or value.get("spacegroup")
            or value.get("space_group")
            or value.get("name")
        )
        number = _coerce_text(
            value.get("number")
            or value.get("spacegroup_number")
            or value.get("international_number")
        )
        if symbol and number:
            return f"{symbol} ({number})"
        return symbol or number

    if isinstance(value, (list, tuple, set)):
        for entry in value:
            formatted = _format_spacegroup_value(entry)
            if formatted:
                return formatted
        return None

    return _coerce_text(value)


def _extract_node_hover_metadata(node_payload: dict[str, Any], pk: int) -> NodeHoverMetadataResponse:
    formula = _coerce_text(node_payload.get("formula") or node_payload.get("chemical_formula"))
    if formula is None:
        formula = _coerce_text(
            _find_first_named_value(
                node_payload,
                {
                    "formula",
                    "chemical_formula",
                    "formula_hill",
                    "formula_reduced",
                    "reduced_formula",
                },
            )
        )

    node_type = _coerce_text(node_payload.get("node_type") or node_payload.get("type"))
    if node_type is None:
        node_type = _coerce_text(
            _find_first_named_value(
                node_payload,
                {"node_type", "type"},
            )
        )

    raw_spacegroup = _find_first_named_value(
        node_payload,
        {
            "spacegroup",
            "space_group",
            "spacegroup_symbol",
            "spacegroup_number",
            "international_symbol",
            "international_number",
            "symmetry",
        },
    )
    spacegroup = _format_spacegroup_value(raw_spacegroup)

    return NodeHoverMetadataResponse(
        pk=pk,
        formula=formula,
        spacegroup=spacegroup,
        node_type=node_type or "Unknown",
    )


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


def _get_frontend_group_labels() -> list[str]:
    if not hub.current_profile:
        hub.start()
    return list_group_labels()


def _get_frontend_nodes(
    limit: int = 15,
    group_label: str | None = None,
    node_type: str | None = None,
) -> list[dict[str, Any]]:
    if not hub.current_profile:
        hub.start()
    return get_recent_nodes(limit=limit, group_label=group_label, node_type=node_type)


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


@router.post("/submission/submit", tags=[WORKER_PROXY_TAG])
async def submit_bridge_workchain(request: Request, payload: SubmissionDraftRequest):
    if not payload.draft:
        raise HTTPException(status_code=422, detail="Submission draft is required")

    draft_payload = payload.draft
    if isinstance(draft_payload, list):
        if len(draft_payload) == 0:
            raise HTTPException(status_code=422, detail="Submission draft list cannot be empty")

        submitted_pks: list[int] = []
        responses: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        for index, draft_item in enumerate(draft_payload):
            if not isinstance(draft_item, dict) or not draft_item:
                failures.append(
                    {
                        "index": index,
                        "error": "Submission draft is required",
                    }
                )
                continue
            try:
                raw = await request_json("POST", "/submission/submit", json={"draft": draft_item})
                response = format_single_submission_response(raw)
                response_pk = _extract_submitted_pk(response)
                if response_pk is not None:
                    submitted_pks.append(response_pk)
                responses.append(
                    {
                        "index": index,
                        "response": response,
                    }
                )
            except BridgeOfflineError as exc:
                failures.append(
                    {
                        "index": index,
                        "status_code": 503,
                        "error": str(exc),
                    }
                )
            except BridgeAPIError as exc:
                detail = exc.payload if isinstance(exc.payload, dict) else {"error": exc.message, "details": exc.payload}
                failures.append(
                    {
                        "index": index,
                        "status_code": max(400, int(exc.status_code or 502)),
                        "detail": detail,
                    }
                )

        if submitted_pks:
            _clear_pending_submission_memory(request.app.state)
        elif failures:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "Batch submission failed",
                    "failures": failures,
                },
            )

        return format_batch_submission_response(submitted_pks, responses, failures)

    try:
        raw = await request_json("POST", "/submission/submit", json={"draft": draft_payload})
        response = format_single_submission_response(raw)
        _clear_pending_submission_memory(request.app.state)
        return response
    except BridgeOfflineError as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc
    except BridgeAPIError as exc:
        detail = exc.payload if isinstance(exc.payload, dict) else {"error": exc.message, "details": exc.payload}
        raise HTTPException(status_code=max(400, int(exc.status_code or 502)), detail=detail) from exc


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


@router.get("/frontend/bootstrap", tags=[FRONTEND_TAG])
async def frontend_bootstrap(request: Request):
    state = request.app.state
    try:
        processes = _get_frontend_nodes(limit=15)
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.bootstrap.processes.failed", error=str(error)))
        processes = []

    try:
        groups = _get_frontend_group_labels()
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.bootstrap.groups.failed", error=str(error)))
        groups = []

    available_models = _get_available_models(state)
    selected_model = _get_selected_model(state, available_models)
    log_version, log_lines = get_log_buffer_snapshot(limit=240)
    chat_history = serialize_chat_history(get_chat_history(state))

    return {
        "processes": _serialize_processes(processes),
        "groups": _serialize_group_labels(groups),
        "chat": {
            "messages": chat_history,
            "version": int(getattr(state, "chat_version", 0)),
        },
        "logs": {
            "version": log_version,
            "lines": log_lines[-160:],
        },
        "models": available_models,
        "selected_model": selected_model,
        "quick_prompts": [{"label": label, "prompt": prompt} for label, prompt in QUICK_PROMPTS],
    }


@router.get("/frontend/groups", tags=[FRONTEND_TAG])
async def frontend_groups():
    try:
        items = _get_frontend_group_labels()
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.groups.failed", error=str(error)))
        items = []
    return {"items": _serialize_group_labels(items)}


@router.post("/frontend/archives/upload", tags=[FRONTEND_TAG])
async def frontend_upload_archive(file: UploadFile = File(...)):
    filename = file.filename or "archive.aiida"
    extension = Path(filename).suffix.lower()
    if extension not in ARCHIVE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported archive format")

    upload_root = Path(tempfile.gettempdir()) / "sabr-aiida-uploads"
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
):
    try:
        processes = _get_frontend_nodes(limit=limit, group_label=group_label, node_type=node_type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        logger.exception(log_event("aiida.frontend.processes.failed", error=str(error)))
        processes = []
    return {"items": _serialize_processes(processes)}


@router.get(
    "/frontend/nodes/{pk}/metadata",
    response_model=NodeHoverMetadataResponse,
    tags=[FRONTEND_TAG],
)
async def frontend_node_hover_metadata(pk: int = ApiPath(..., ge=1)) -> NodeHoverMetadataResponse:
    return _get_node_hover_metadata(pk)


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
    history = serialize_chat_history(get_chat_history(state))
    return {
        "version": int(getattr(state, "chat_version", 0)),
        "messages": history,
    }


@router.get("/frontend/chat/stream", tags=[FRONTEND_TAG])
async def frontend_chat_stream(request: Request):
    state = request.app.state

    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.chat_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.chat_stream.disconnected", stream_id=stream_id))
                break

            try:
                version = int(getattr(state, "chat_version", 0))
                history = serialize_chat_history(get_chat_history(state))
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 10)
                if should_push:
                    yield {
                        "event": "chat",
                        "data": json.dumps({"version": version, "messages": history}),
                    }
                    last_version = version
                    heartbeat_ts = now
            except Exception as error:  # noqa: BLE001
                logger.exception(
                    log_event("aiida.frontend.chat_stream.failed", stream_id=stream_id, error=str(error))
                )
                yield {"event": "chat", "data": json.dumps({"version": -1, "messages": []})}

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
