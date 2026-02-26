from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import BridgeAPIError, BridgeOfflineError, request_json_sync


def get_recent_processes(limit: int = 5) -> list[dict[str, Any]]:
    try:
        payload = request_json_sync("GET", "/management/recent-processes", params={"limit": int(limit)}, timeout=6.0)
    except (BridgeOfflineError, BridgeAPIError):
        return []
    except Exception:  # noqa: BLE001
        return []

    if isinstance(payload, dict):
        items = payload.get("items")
        return items if isinstance(items, list) else []
    return payload if isinstance(payload, list) else []


def list_group_labels(search: str | None = None) -> list[str]:
    params = {"search": search} if search else None
    try:
        payload = request_json_sync("GET", "/management/groups/labels", params=params, timeout=6.0)
    except (BridgeOfflineError, BridgeAPIError):
        return []
    except Exception:  # noqa: BLE001
        return []

    if isinstance(payload, dict):
        items = payload.get("items")
        return [str(item) for item in items] if isinstance(items, list) else []
    return [str(item) for item in payload] if isinstance(payload, list) else []


def get_recent_nodes(
    limit: int = 15,
    group_label: str | None = None,
    node_type: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": int(limit)}
    if group_label:
        params["group_label"] = group_label
    if node_type:
        params["node_type"] = node_type

    try:
        payload = request_json_sync("GET", "/management/recent-nodes", params=params, timeout=8.0)
    except (BridgeOfflineError, BridgeAPIError):
        return []
    except Exception:  # noqa: BLE001
        return []

    if isinstance(payload, dict):
        items = payload.get("items")
        return items if isinstance(items, list) else []
    return payload if isinstance(payload, list) else []


def get_context_nodes(node_ids: list[int]) -> list[dict[str, Any]]:
    ids = [int(pk) for pk in node_ids if isinstance(pk, int) or str(pk).isdigit()]
    if not ids:
        return []

    try:
        payload = request_json_sync("POST", "/management/nodes/context", json={"ids": ids[:30]}, timeout=8.0)
    except (BridgeOfflineError, BridgeAPIError):
        return []
    except Exception:  # noqa: BLE001
        return []

    if isinstance(payload, dict):
        items = payload.get("items")
        return items if isinstance(items, list) else []
    return payload if isinstance(payload, list) else []
