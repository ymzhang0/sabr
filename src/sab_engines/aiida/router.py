from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
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
from .service import (
    get_context_nodes,
    get_recent_nodes,
    list_group_labels,
    hub,
)

FRONTEND_TAG = "AiiDA-Frontend-API"
WORKER_PROXY_TAG = "AiiDA-Worker-Proxy"

router = APIRouter()
DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
QUICK_PROMPTS: list[tuple[str, str]] = [
    ("Check Profile", "check the current profile"),
    ("List Groups", "list all groups in current profile"),
    ("DB Summary", "show database summary"),
]
ARCHIVE_EXTENSIONS = {".aiida", ".zip"}


class FrontendChatRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=12000)
    model_name: str | None = None
    context_archive: str | None = None
    context_node_ids: list[int] | None = None
    context_pks: list[int] | None = None
    metadata: dict[str, Any] | None = None


class FrontendStopChatRequest(BaseModel):
    turn_id: int | None = None


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


def _normalize_process_state(state: str | None) -> str:
    return str(state or "unknown").strip().lower()


def _state_to_status_color(state: str | None) -> str:
    normalized = _normalize_process_state(state)
    if normalized in {"running", "created", "waiting"}:
        return "running"
    if normalized in {"finished", "completed"}:
        return "success"
    if normalized in {"failed", "excepted", "killed"}:
        return "error"
    return "idle"


def _serialize_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for process in processes:
        process_state_raw = process.get("process_state")
        state = str(process_state_raw or process.get("state") or "unknown")
        process_label_raw = process.get("process_label")
        try:
            pk = int(process.get("pk", 0))
        except (TypeError, ValueError):
            pk = 0
        formula = process.get("formula")
        serialized: dict[str, Any] = {
            "pk": pk,
            "label": str(process.get("label") or "Unknown Task"),
            "state": state,
            "status_color": _state_to_status_color(state),
            "node_type": str(process.get("node_type") or "Node"),
            "process_state": str(process_state_raw) if process_state_raw is not None else None,
            "formula": str(formula) if formula else None,
        }
        if process_label_raw:
            serialized["process_label"] = str(process_label_raw)
        if "preview" in process:
            serialized["preview"] = process.get("preview")
        if "preview_info" in process:
            serialized["preview_info"] = process.get("preview_info")
        payload.append(serialized)
    return payload


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


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        values = value
    elif isinstance(value, dict):
        values = value.keys()
    elif value is None:
        values = []
    else:
        values = [value]
    result: list[str] = []
    for item in values:
        text = _coerce_text(item)
        if text:
            result.append(text)
    return result


def _extract_filename_list(raw: Any, limit: int = 5) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        for key in ("files", "filenames", "items", "listing", "entries", "paths"):
            if key in raw:
                return _extract_filename_list(raw.get(key), limit=limit)
        # map-style fallback: {"file.txt": {...}, ...}
        if raw:
            return _extract_filename_list(list(raw.keys()), limit=limit)
        return []
    if isinstance(raw, (list, tuple, set)):
        values: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                name = _coerce_text(
                    item.get("name")
                    or item.get("filename")
                    or item.get("path")
                    or item.get("label")
                )
            else:
                name = _coerce_text(item)
            if name:
                values.append(name)
            if len(values) >= limit:
                break
        return values[:limit]
    single = _coerce_text(raw)
    return [single] if single else []


def _normalize_link_entry(raw: Any, fallback_label: str | None = None) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        nested_node: dict[str, Any] | None = None
        for key in ("node", "target", "source", "data", "value"):
            candidate = raw.get(key)
            if isinstance(candidate, dict):
                nested_node = candidate
                break

        pk = _coerce_int(
            raw.get("pk")
            or raw.get("node_pk")
            or raw.get("id")
            or (nested_node or {}).get("pk")
            or (nested_node or {}).get("id")
        )
        if pk is None:
            return None

        node_type = _coerce_text(
            raw.get("node_type")
            or raw.get("type")
            or raw.get("entry_type")
            or (nested_node or {}).get("node_type")
            or (nested_node or {}).get("type")
            or (nested_node or {}).get("entry_type")
            or "Node"
        )
        if not node_type:
            node_type = "Node"

        link_label = _coerce_text(
            raw.get("link_label")
            or raw.get("label")
            or raw.get("linkname")
            or raw.get("name")
            or fallback_label
            or f"link_{pk}"
        )
        return {
            "link_label": link_label or f"link_{pk}",
            "node_type": node_type,
            "pk": pk,
        }

    pk = _coerce_int(raw)
    if pk is None:
        return None
    return {
        "link_label": fallback_label or f"link_{pk}",
        "node_type": "Node",
        "pk": pk,
    }


def _normalize_links_payload(raw: Any, prefix: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if raw is None:
        return normalized

    if isinstance(raw, (list, tuple, set)):
        for idx, item in enumerate(raw, start=1):
            entry = _normalize_link_entry(item, fallback_label=f"{prefix}_{idx}")
            if entry:
                normalized.append(entry)
        return normalized

    if isinstance(raw, dict):
        direct_entry = _normalize_link_entry(raw, fallback_label=prefix)
        if direct_entry:
            return [direct_entry]

        container_keys = {"items", "links", "data", "entries", "results", "nodes"}
        for container_key in container_keys:
            if container_key in raw:
                normalized.extend(_normalize_links_payload(raw.get(container_key), prefix))

        for key, value in raw.items():
            if key in container_keys:
                continue
            fallback_label = _coerce_text(key) or prefix
            entry = _normalize_link_entry(value, fallback_label=fallback_label)
            if entry:
                normalized.append(entry)
        return normalized

    entry = _normalize_link_entry(raw, fallback_label=prefix)
    if entry:
        normalized.append(entry)
    return normalized


def _dedupe_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for link in links:
        pk = _coerce_int(link.get("pk"))
        if pk is None:
            continue
        node_type = _coerce_text(link.get("node_type")) or "Node"
        link_label = _coerce_text(link.get("link_label")) or f"link_{pk}"
        key = (pk, node_type, link_label)
        if key in seen:
            continue
        seen.add(key)
        payload: dict[str, Any] = {
            "link_label": link_label,
            "node_type": node_type,
            "pk": pk,
        }
        preview = link.get("preview")
        if isinstance(preview, dict) and preview:
            payload["preview"] = preview
        deduped.append(payload)
    return deduped


def _extract_directional_links(payload: dict[str, Any], direction: Literal["inputs", "outputs"]) -> list[dict[str, Any]]:
    if direction == "inputs":
        direct_keys = ("inputs", "incoming", "incoming_links", "input_links", "inbound")
        nested_keys = ("inputs", "incoming", "inbound")
    else:
        direct_keys = ("outputs", "outgoing", "outgoing_links", "output_links", "outbound")
        nested_keys = ("outputs", "outgoing", "outbound")

    links: list[dict[str, Any]] = []
    for key in direct_keys:
        if key in payload:
            links.extend(_normalize_links_payload(payload.get(key), direction[:-1]))

    links_block = payload.get("links")
    if isinstance(links_block, dict):
        for key in nested_keys:
            if key in links_block:
                links.extend(_normalize_links_payload(links_block.get(key), direction[:-1]))

    provenance_block = payload.get("provenance")
    if isinstance(provenance_block, dict):
        for key in nested_keys:
            if key in provenance_block:
                links.extend(_normalize_links_payload(provenance_block.get(key), direction[:-1]))

    return _dedupe_links(links)


def _collect_tree_node_ids(tree_root: Any) -> list[int]:
    if not isinstance(tree_root, dict):
        return []
    node_ids: list[int] = []
    seen: set[int] = set()

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        pk = _coerce_int(node.get("pk"))
        if pk is not None and pk not in seen:
            seen.add(pk)
            node_ids.append(pk)
        children = node.get("children")
        if isinstance(children, dict):
            for child in children.values():
                walk(child)
        elif isinstance(children, list):
            for child in children:
                walk(child)

    walk(tree_root)
    return node_ids


def _attach_tree_links(
    tree_root: Any,
    links_by_pk: dict[int, tuple[list[dict[str, Any]], list[dict[str, Any]]]],
) -> None:
    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        pk = _coerce_int(node.get("pk"))
        if pk is not None:
            input_links, output_links = links_by_pk.get(pk, ([], []))
            node["inputs"] = input_links
            node["outputs"] = output_links
        children = node.get("children")
        if isinstance(children, dict):
            for child in children.values():
                walk(child)
        elif isinstance(children, list):
            for child in children:
                walk(child)

    walk(tree_root)


def _extract_remote_preview(payload: dict[str, Any]) -> dict[str, Any] | None:
    remote_path = _coerce_text(payload.get("remote_path") or payload.get("path"))
    computer_name = _coerce_text(payload.get("computer_name") or payload.get("computer_label"))
    computer = payload.get("computer")
    if not computer_name and isinstance(computer, dict):
        computer_name = _coerce_text(
            computer.get("label")
            or computer.get("name")
            or computer.get("hostname")
            or computer.get("host")
        )
    if not computer_name:
        computer_name = _coerce_text(payload.get("hostname") or payload.get("host"))
    if not remote_path and not computer_name:
        return None
    return {
        "remote_path": remote_path,
        "computer_name": computer_name,
    }


def _extract_folder_preview(payload: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[Any] = [
        payload.get("filenames"),
        payload.get("files"),
        payload.get("items"),
        payload.get("listing"),
        payload.get("entries"),
        payload.get("paths"),
        payload.get("children"),
        payload.get("objects"),
    ]

    repository = payload.get("repository")
    if repository is not None:
        candidates.append(repository)
        if isinstance(repository, dict):
            for key in ("filenames", "files", "items", "listing", "entries", "paths"):
                if key in repository:
                    candidates.append(repository.get(key))

    for candidate in candidates:
        filenames = _extract_filename_list(candidate, limit=5)
        if filenames:
            return {"filenames": filenames[:5]}
    return None


def _extract_xy_preview(payload: dict[str, Any]) -> dict[str, Any] | None:
    x_label = _coerce_text(payload.get("x_label") or payload.get("x_name") or payload.get("x"))
    x_length = _coerce_int(payload.get("x_length") or payload.get("x_len") or payload.get("x_size"))

    y_labels = _coerce_string_list(payload.get("y_labels") or payload.get("y_names") or payload.get("y"))
    y_arrays: list[dict[str, Any]] = []

    y_lengths_raw = payload.get("y_lengths")
    y_lengths_by_label: dict[str, int | None] = {}
    if isinstance(y_lengths_raw, dict):
        for key, value in y_lengths_raw.items():
            y_key = _coerce_text(key)
            if y_key:
                y_lengths_by_label[y_key] = _coerce_int(value)
    elif isinstance(y_lengths_raw, (list, tuple)):
        for idx, value in enumerate(y_lengths_raw):
            if idx < len(y_labels):
                y_lengths_by_label[y_labels[idx]] = _coerce_int(value)

    arrays_raw = payload.get("arrays")
    if isinstance(arrays_raw, list):
        for item in arrays_raw:
            if not isinstance(item, dict):
                continue
            label = _coerce_text(item.get("name") or item.get("label"))
            length = _coerce_int(item.get("length") or item.get("size"))
            if length is None and isinstance(item.get("shape"), (list, tuple)):
                shape = item.get("shape")
                if shape:
                    length = _coerce_int(shape[0])
            if label:
                if label == x_label and x_length is None:
                    x_length = length
                elif label in y_labels:
                    y_lengths_by_label[label] = length

    for label in y_labels:
        y_arrays.append({"label": label, "length": y_lengths_by_label.get(label)})

    if not x_label and not y_arrays:
        return None
    return {
        "x_label": x_label,
        "x_length": x_length,
        "y_arrays": y_arrays,
    }


def _extract_preview_for_node_type(node_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if node_type == "RemoteData":
        return _extract_remote_preview(payload)
    if node_type == "FolderData":
        return _extract_folder_preview(payload)
    if node_type == "XyData":
        return _extract_xy_preview(payload)
    return None


async def _request_optional_json(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any | None:
    try:
        return await request_json(method, path, params=params)
    except (BridgeOfflineError, BridgeAPIError):
        return None
    except Exception:
        return None


async def _fetch_node_payload(pk: int, cache: dict[int, dict[str, Any] | None]) -> dict[str, Any] | None:
    if pk in cache:
        return cache[pk]
    payload = await _request_optional_json("GET", f"/management/nodes/{pk}")
    cache[pk] = payload if isinstance(payload, dict) else None
    return cache[pk]


async def _fetch_data_node_payload(pk: int, cache: dict[int, dict[str, Any] | None]) -> dict[str, Any] | None:
    if pk in cache:
        return cache[pk]
    payload = await _request_optional_json("GET", f"/data/node/{pk}")
    cache[pk] = payload if isinstance(payload, dict) else None
    return cache[pk]


async def _fetch_repository_filenames(pk: int, cache: dict[int, list[str]]) -> list[str]:
    if pk in cache:
        return cache[pk]
    payload = await _request_optional_json("GET", f"/data/repository/{pk}/files", params={"source": "folder"})
    if payload is None:
        payload = await _request_optional_json("GET", f"/data/repository/{pk}/files")
    filenames = _extract_filename_list(payload, limit=5)
    cache[pk] = filenames[:5]
    return cache[pk]


async def _enrich_link_preview(
    link: dict[str, Any],
    node_payload_cache: dict[int, dict[str, Any] | None],
    data_payload_cache: dict[int, dict[str, Any] | None],
    repo_listing_cache: dict[int, list[str]],
) -> None:
    node_type = _coerce_text(link.get("node_type")) or "Node"
    if node_type not in {"RemoteData", "FolderData", "XyData"}:
        return
    pk = _coerce_int(link.get("pk"))
    if pk is None:
        return

    preview: dict[str, Any] | None = None
    node_payload = await _fetch_node_payload(pk, node_payload_cache)
    if node_payload:
        preview = _extract_preview_for_node_type(node_type, node_payload)

    if not preview:
        data_payload = await _fetch_data_node_payload(pk, data_payload_cache)
        if data_payload:
            preview = _extract_preview_for_node_type(node_type, data_payload)

    if node_type == "FolderData":
        filenames = preview.get("filenames") if isinstance(preview, dict) else None
        if not filenames:
            filenames = await _fetch_repository_filenames(pk, repo_listing_cache)
            if filenames:
                preview = dict(preview or {})
                preview["filenames"] = filenames[:5]

    if preview:
        link["preview"] = preview


async def _enrich_links_with_previews(
    links: list[dict[str, Any]],
    *,
    node_payload_cache: dict[int, dict[str, Any] | None],
    data_payload_cache: dict[int, dict[str, Any] | None],
    repo_listing_cache: dict[int, list[str]],
) -> None:
    tasks = [
        _enrich_link_preview(
            link,
            node_payload_cache=node_payload_cache,
            data_payload_cache=data_payload_cache,
            repo_listing_cache=repo_listing_cache,
        )
        for link in links
    ]
    if tasks:
        await asyncio.gather(*tasks)


async def _enrich_process_detail_payload(payload: dict[str, Any]) -> dict[str, Any]:
    detail = payload
    summary = detail.get("summary")
    root_pk = _coerce_int(summary.get("pk")) if isinstance(summary, dict) else None
    tree_root = (
        detail.get("workchain", {}).get("provenance_tree")
        if isinstance(detail.get("workchain"), dict)
        else None
    )
    tree_node_ids = _collect_tree_node_ids(tree_root)

    node_ids: list[int] = []
    if root_pk is not None:
        node_ids.append(root_pk)
    for pk in tree_node_ids:
        if pk not in node_ids:
            node_ids.append(pk)

    node_payload_cache: dict[int, dict[str, Any] | None] = {}
    data_payload_cache: dict[int, dict[str, Any] | None] = {}
    repo_listing_cache: dict[int, list[str]] = {}
    links_by_pk: dict[int, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}

    if node_ids:
        summaries = await asyncio.gather(*[_fetch_node_payload(pk, node_payload_cache) for pk in node_ids])
        for pk, node_payload in zip(node_ids, summaries):
            if isinstance(node_payload, dict):
                input_links = _extract_directional_links(node_payload, "inputs")
                output_links = _extract_directional_links(node_payload, "outputs")
            else:
                input_links = []
                output_links = []
            links_by_pk[pk] = (input_links, output_links)

    detail_inputs = _extract_directional_links(detail, "inputs")
    detail_outputs = _extract_directional_links(detail, "outputs")
    if root_pk is not None and root_pk in links_by_pk:
        root_input_links, root_output_links = links_by_pk[root_pk]
        detail_inputs = _dedupe_links(detail_inputs + root_input_links)
        detail_outputs = _dedupe_links(detail_outputs + root_output_links)
    else:
        detail_inputs = _dedupe_links(detail_inputs)
        detail_outputs = _dedupe_links(detail_outputs)

    all_link_lists: list[list[dict[str, Any]]] = [detail_inputs, detail_outputs]
    for input_links, output_links in links_by_pk.values():
        all_link_lists.append(input_links)
        all_link_lists.append(output_links)

    await asyncio.gather(
        *[
            _enrich_links_with_previews(
                links,
                node_payload_cache=node_payload_cache,
                data_payload_cache=data_payload_cache,
                repo_listing_cache=repo_listing_cache,
            )
            for links in all_link_lists
            if links
        ]
    )

    detail["inputs"] = detail_inputs
    detail["outputs"] = detail_outputs
    if isinstance(tree_root, dict):
        _attach_tree_links(tree_root, links_by_pk)
    return detail


def _fetch_context_nodes(context_node_ids: list[int]) -> list[dict[str, Any]]:
    if not context_node_ids:
        return []
    if not hub.current_profile:
        hub.start()
    return get_context_nodes(context_node_ids)


def _sanitize_upload_name(filename: str) -> str:
    safe = Path(filename).name.replace(" ", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch in {"-", "_", "."}) or "archive.aiida"


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

    client = genai.Client(api_key=api_key)
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
        "groups": groups,
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
    return {"items": items}


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
