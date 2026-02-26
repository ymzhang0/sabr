"""Async bridge proxy for BandsData extraction."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def get_bands_plot_data(pk: int) -> dict[str, Any] | str:
    """Retrieve plot-ready bands payload from worker (`GET /data/bands/{pk}`)."""
    try:
        payload = await request_json("GET", f"/data/bands/{int(pk)}")
        return payload if isinstance(payload, dict) else {"data": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)
