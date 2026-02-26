"""Async bridge proxies for RemoteData directory/file access."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def list_remote_files(pk: int | str) -> list[str] | dict[str, Any] | str:
    """List files in a RemoteData node (`GET /data/remote/{pk}/files`)."""
    try:
        payload = await request_json("GET", f"/data/remote/{pk}/files")
        if isinstance(payload, dict):
            files = payload.get("files")
            return files if isinstance(files, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_remote_file_content(pk: int | str, filename: str) -> str | dict[str, Any]:
    """Read one file from RemoteData (`GET /data/remote/{pk}/files/{filename}`)."""
    try:
        payload = await request_json("GET", f"/data/remote/{pk}/files/{filename}")
        if isinstance(payload, dict):
            content = payload.get("content")
            return str(content) if isinstance(content, str) else payload
        return str(payload)
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)
