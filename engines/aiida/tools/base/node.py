from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def get_node_summary(node_pk: int) -> dict[str, Any] | str:
    """Return a structured node summary from the worker bridge for reasoning/UI use."""
    try:
        payload = await request_json("GET", f"/management/nodes/{int(node_pk)}")
        return payload if isinstance(payload, dict) else {"data": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def serialize_node(node_pk: int) -> dict[str, Any] | str:
    """Compatibility wrapper that resolves to the worker-provided node summary payload."""
    return await get_node_summary(node_pk)
