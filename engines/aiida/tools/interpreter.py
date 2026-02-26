"""Async bridge proxy for worker-side Python execution helpers."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def run_python_code(script: str) -> str | dict[str, Any]:
    """
    Execute ad-hoc Python/AiiDA logic on the worker (`POST /management/run-python`).

    Returns stdout/stderr capture on success and structured bridge errors otherwise.
    """
    try:
        payload = await request_json("POST", "/management/run-python", json={"script": script})
        if isinstance(payload, dict):
            if payload.get("success"):
                return str(payload.get("output") or "Code executed successfully (No output).")
            return {
                "error": str(payload.get("error") or "Worker script execution failed"),
                "output": payload.get("output"),
            }
        return str(payload)
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)
