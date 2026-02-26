"""Async bridge proxy for repository/folder file reading."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def get_node_file_content(pk: int | str, filename: str, source: str = "folder") -> str | dict[str, Any]:
    """Read text content from node storage (`GET /data/repository/{pk}/files/{filename}`)."""
    try:
        payload = await request_json(
            "GET",
            f"/data/repository/{pk}/files/{filename}",
            params={"source": source},
        )
        if isinstance(payload, dict):
            content = payload.get("content")
            return str(content) if isinstance(content, str) else payload
        return str(payload)
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)
