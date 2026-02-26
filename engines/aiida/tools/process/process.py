"""Async process inspection proxies backed by aiida-worker endpoints."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def inspect_process(identifier: str) -> dict[str, Any] | str:
    """Inspect any ProcessNode by PK/UUID (`GET /process/{identifier}`)."""
    try:
        payload = await request_json("GET", f"/process/{identifier}")
        return payload if isinstance(payload, dict) else {"result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_process_log(pk: int) -> dict[str, Any] | str:
    """Fetch merged reports/stderr for one process (`GET /process/{pk}/logs`)."""
    try:
        payload = await request_json("GET", f"/process/{int(pk)}/logs")
        return payload if isinstance(payload, dict) else {"logs": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def fetch_recent_processes(limit: int = 15) -> list[dict[str, Any]] | dict[str, Any] | str:
    """Fetch recent processes (`GET /management/recent-processes`) for quick status snapshots."""
    try:
        payload = await request_json("GET", "/management/recent-processes", params={"limit": int(limit)})
        if isinstance(payload, dict):
            items = payload.get("items")
            return items if isinstance(items, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)
