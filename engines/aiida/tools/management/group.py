"""Async bridge proxies for group inspection and group-scoped process lookups."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def inspect_group(group_name: str, limit: int = 20) -> dict[str, Any] | str:
    """Inspect one group in detail (`GET /management/groups/{group_name}`) with node attributes/extras."""
    try:
        payload = await request_json(
            "GET",
            f"/management/groups/{group_name}",
            params={"limit": int(limit)},
        )
        return payload if isinstance(payload, dict) else {"group": group_name, "result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def fetch_group_nodes(group_name: str, limit: int = 100) -> list[dict[str, Any]] | dict[str, Any] | str:
    """Return up to `limit` serialized nodes in a group using worker inspection endpoint."""
    result = await inspect_group(group_name, limit=limit)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        nodes = result.get("nodes")
        return nodes if isinstance(nodes, list) else result
    return result


async def fetch_group_processes(group_label: str, limit: int = 20, exclude_import: bool = True) -> list[dict[str, Any]] | dict[str, Any] | str:  # noqa: ARG001
    """Fetch recent process-like nodes constrained to a group (`GET /management/recent-nodes`)."""
    try:
        payload = await request_json(
            "GET",
            "/management/recent-nodes",
            params={"limit": int(limit), "group_label": group_label, "node_type": "WorkChainNode"},
        )
        if isinstance(payload, dict):
            items = payload.get("items")
            return items if isinstance(items, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def create_group(group_label: str) -> dict[str, Any] | str:
    """Create-group helper (currently unsupported): returns a structured bridge error placeholder."""
    return {
        "error": "Group creation is not exposed by the current AiiDA Worker API.",
        "group_label": group_label,
    }
