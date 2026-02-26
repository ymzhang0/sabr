"""Async submission/introspection proxies for the aiida-worker bridge."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


def _normalize_plugins_payload(payload: Any) -> list[str]:
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("plugins"), list):
            values = payload["plugins"]
        elif isinstance(payload.get("items"), list):
            values = payload["items"]
        else:
            values = []
    else:
        values = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return sorted(normalized)


async def list_remote_plugins() -> list[str] | str:
    """Source of truth for available WorkChains (`GET /submission/plugins`)."""
    try:
        payload = await request_json("GET", "/submission/plugins")
        return _normalize_plugins_payload(payload)
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_remote_workchain_spec(entry_point: str) -> dict[str, Any] | str:
    """Fetch WorkChain input spec (`GET /submission/spec/{entry_point}`)."""
    cleaned = (entry_point or "").strip()
    if not cleaned:
        return "Please provide a valid WorkChain entry point name."

    try:
        payload = await request_json("GET", f"/submission/spec/{quote(cleaned, safe='')}")
        return payload if isinstance(payload, dict) else {"spec": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def inspect_lab_infrastructure() -> dict[str, Any] | str:
    """Inspect worker profile/daemon/computers/codes before submission."""
    try:
        system_payload = await request_json("GET", "/system/info")
        resources_payload = await request_json("GET", "/resources")
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)

    if not isinstance(system_payload, dict) or not isinstance(resources_payload, dict):
        return {"error": "Bridge returned invalid infrastructure payload"}

    computers = resources_payload.get("computers") if isinstance(resources_payload.get("computers"), list) else []
    codes = resources_payload.get("codes") if isinstance(resources_payload.get("codes"), list) else []

    return {
        "profile": str(system_payload.get("profile") or "unknown"),
        "daemon_status": bool(system_payload.get("daemon_status", False)),
        "counts": system_payload.get("counts") if isinstance(system_payload.get("counts"), dict) else {},
        "computers": computers,
        "codes": codes,
        "code_targets": [
            f"{code.get('label')}@{code.get('computer_label')}"
            if isinstance(code, dict) and code.get("computer_label")
            else str(code.get("label") if isinstance(code, dict) else code)
            for code in codes
        ],
    }


async def inspect_workchain_spec(entry_point_name: str):
    """Inspect WorkChain spec by delegating to `get_remote_workchain_spec`."""
    return await get_remote_workchain_spec(entry_point_name)


async def draft_workchain_builder(
    workchain_label: str,
    structure_pk: int,
    code_label: str,
    protocol: str = "moderate",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any] | str:
    """Request builder draft creation from worker (`POST /submission/draft-builder`)."""
    body = {
        "workchain": workchain_label,
        "structure_pk": int(structure_pk),
        "code": code_label,
        "protocol": protocol,
        "overrides": overrides or {},
    }

    try:
        payload = await request_json("POST", "/submission/draft-builder", json=body)
        return payload if isinstance(payload, dict) else {"draft": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def submit_workchain_builder(draft_data: dict[str, Any]) -> dict[str, Any] | str:
    """Submit a previously drafted builder (`POST /submission/submit`)."""
    try:
        payload = await request_json("POST", "/submission/submit", json={"draft": draft_data})
        return payload if isinstance(payload, dict) else {"result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def submit_workflow(draft_data: dict[str, Any]) -> dict[str, Any] | str:
    """
    Consistent submission interface for agents.

    Calls `POST /submission/submit` with a builder draft payload and returns
    the worker submission receipt (`pk`, `uuid`, `state`) on success.
    """
    return await submit_workchain_builder(draft_data)
