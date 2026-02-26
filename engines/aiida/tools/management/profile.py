"""Async bridge proxies for profile, group, and database management metadata."""

from __future__ import annotations

from typing import Any

from engines.aiida.bridge_client import (
    OFFLINE_WORKER_MESSAGE,
    BridgeOfflineError,
    format_bridge_error,
    request_json,
)


async def list_system_profiles() -> dict[str, Any] | str:
    """List configured profiles from the worker (`GET /management/profiles`)."""
    try:
        payload = await request_json("GET", "/management/profiles")
        return payload if isinstance(payload, dict) else {"profiles": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def list_local_archives(path: str = ".") -> list[str] | dict[str, Any] | str:
    """List local `.aiida`/`.zip` archives visible to the worker (`GET /management/archives/local`)."""
    try:
        payload = await request_json("GET", "/management/archives/local", params={"path": path})
        if isinstance(payload, dict):
            archives = payload.get("archives")
            return archives if isinstance(archives, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def switch_profile(profile: str) -> dict[str, Any] | str:
    """Switch active profile in the worker (`POST /management/profiles/switch`)."""
    try:
        payload = await request_json("POST", "/management/profiles/switch", json={"profile": profile})
        return payload if isinstance(payload, dict) else {"status": "switched", "result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def load_archive_profile(filepath: str) -> dict[str, Any] | str:
    """Load an archive-backed profile in the worker (`POST /management/profiles/load-archive`)."""
    try:
        payload = await request_json("POST", "/management/profiles/load-archive", json={"path": filepath})
        return payload if isinstance(payload, dict) else {"status": "loaded", "result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_unified_source_map(target: str | None = None) -> dict[str, Any] | str:
    """Build profile/archive group map from worker (`GET /management/source-map`)."""
    params = {"target": target} if target else None
    try:
        payload = await request_json("GET", "/management/source-map", params=params)
        return payload if isinstance(payload, dict) else {"result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_statistics(profile_name: str | None = None) -> dict[str, Any] | str:
    """Get consolidated infra/db statistics from worker (`GET /management/statistics`)."""
    if profile_name:
        switched = await switch_profile(profile_name)
        if isinstance(switched, str):
            return switched
        if isinstance(switched, dict) and switched.get("error"):
            return switched

    try:
        payload = await request_json("GET", "/management/statistics")
        return payload if isinstance(payload, dict) else {"statistics": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def list_groups(search_string: str | None = None) -> list[dict[str, Any]] | dict[str, Any] | str:
    """List groups from worker (`GET /management/groups`) with optional substring filter."""
    params = {"search": search_string} if search_string else None
    try:
        payload = await request_json("GET", "/management/groups", params=params)
        if isinstance(payload, dict):
            items = payload.get("items")
            return items if isinstance(items, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_database_summary() -> dict[str, Any] | str:
    """Get compact DB health summary (`GET /management/database/summary`)."""
    try:
        payload = await request_json("GET", "/management/database/summary")
        return payload if isinstance(payload, dict) else {"summary": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_recent_processes(limit: int = 5) -> list[dict[str, Any]] | dict[str, Any] | str:
    """Fetch recent processes from worker (`GET /management/recent-processes`)."""
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


async def list_group_labels(search_string: str | None = None) -> list[str] | dict[str, Any] | str:
    """List group labels for dropdowns (`GET /management/groups/labels`)."""
    params = {"search": search_string} if search_string else None
    try:
        payload = await request_json("GET", "/management/groups/labels", params=params)
        if isinstance(payload, dict):
            items = payload.get("items")
            return items if isinstance(items, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_recent_nodes(
    limit: int = 15,
    group_label: str | None = None,
    node_type: str | None = None,
) -> list[dict[str, Any]] | dict[str, Any] | str:
    """Fetch recent nodes (`GET /management/recent-nodes`) with optional group/type filters."""
    params: dict[str, Any] = {"limit": int(limit)}
    if group_label:
        params["group_label"] = group_label
    if node_type:
        params["node_type"] = node_type

    try:
        payload = await request_json("GET", "/management/recent-nodes", params=params)
        if isinstance(payload, dict):
            items = payload.get("items")
            return items if isinstance(items, list) else payload
        return payload
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def get_default_profile() -> dict[str, Any] | str:
    """Compatibility helper returning default/current profile info from worker metadata."""
    profiles = await list_system_profiles()
    if isinstance(profiles, str):
        return profiles
    if isinstance(profiles, dict):
        return {
            "default_profile": profiles.get("default_profile"),
            "current_profile": profiles.get("current_profile"),
        }
    return {"profiles": profiles}
