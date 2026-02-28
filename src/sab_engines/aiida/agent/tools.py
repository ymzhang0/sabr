"""AiiDA worker proxy tools used by the SABR AiiDA agent.

Thin-client rule: all domain operations are delegated to aiida-worker HTTP APIs.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.sab_engines.aiida.client import (
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
    """List local `.aiida`/`.zip` archives visible to worker (`GET /management/archives/local`)."""
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
    """Switch active profile in worker (`POST /management/profiles/switch`)."""
    try:
        payload = await request_json("POST", "/management/profiles/switch", json={"profile": profile})
        return payload if isinstance(payload, dict) else {"status": "switched", "result": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def load_archive_profile(filepath: str) -> dict[str, Any] | str:
    """Load an archive-backed profile in worker (`POST /management/profiles/load-archive`)."""
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
    """List groups from worker (`GET /management/groups`) with optional filter."""
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
    """Fetch recent processes (`GET /management/recent-processes`)."""
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
    """Fetch recent nodes (`GET /management/recent-nodes`) with optional filters."""
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


async def inspect_group(group_name: str, limit: int = 20) -> dict[str, Any] | str:
    """Inspect one group (`GET /management/groups/{group_name}`) with node attributes/extras."""
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
    """Return up to `limit` serialized nodes in a group."""
    result = await inspect_group(group_name, limit=limit)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        nodes = result.get("nodes")
        return nodes if isinstance(nodes, list) else result
    return result


async def fetch_group_processes(
    group_label: str,
    limit: int = 20,
    exclude_import: bool = True,  # noqa: ARG001
) -> list[dict[str, Any]] | dict[str, Any] | str:
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
    """Create-group helper placeholder (not yet exposed by worker API)."""
    return {
        "error": "Group creation is not exposed by the current AiiDA Worker API.",
        "group_label": group_label,
    }


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
    """Fetch recent processes for quick status snapshots."""
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
    """Inspect WorkChain spec via bridge (`GET /submission/spec/{entry_point}`)."""
    return await get_remote_workchain_spec(entry_point_name)


async def draft_workchain_builder(
    workchain_label: str,
    structure_pk: int,
    code_label: str,
    protocol: str = "moderate",
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any] | str:
    """Request builder draft creation (`POST /submission/draft-builder`)."""
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
    """Consistent submission interface for agents."""
    return await submit_workchain_builder(draft_data)


async def run_python_code(script: str) -> str | dict[str, Any]:
    """Execute ad-hoc Python/AiiDA logic on worker (`POST /management/run-python`)."""
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


async def get_bands_plot_data(pk: int) -> dict[str, Any] | str:
    """Retrieve plot-ready bands payload from worker (`GET /data/bands/{pk}`)."""
    try:
        payload = await request_json("GET", f"/data/bands/{int(pk)}")
        return payload if isinstance(payload, dict) else {"data": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


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


async def get_node_summary(node_pk: int) -> dict[str, Any] | str:
    """Return a structured node summary from worker bridge for reasoning/UI use."""
    try:
        payload = await request_json("GET", f"/management/nodes/{int(node_pk)}")
        return payload if isinstance(payload, dict) else {"data": payload}
    except BridgeOfflineError:
        return OFFLINE_WORKER_MESSAGE
    except Exception as exc:  # noqa: BLE001
        return format_bridge_error(exc)


async def serialize_node(node_pk: int) -> dict[str, Any] | str:
    """Compatibility wrapper that resolves to worker-provided node summary payload."""
    return await get_node_summary(node_pk)


__all__ = [
    "get_default_profile",
    "list_system_profiles",
    "list_local_archives",
    "switch_profile",
    "load_archive_profile",
    "get_statistics",
    "list_groups",
    "get_unified_source_map",
    "get_database_summary",
    "get_recent_processes",
    "list_group_labels",
    "get_recent_nodes",
    "inspect_group",
    "fetch_group_nodes",
    "fetch_group_processes",
    "create_group",
    "inspect_process",
    "get_process_log",
    "fetch_recent_processes",
    "inspect_workchain_spec",
    "list_remote_plugins",
    "get_remote_workchain_spec",
    "inspect_lab_infrastructure",
    "draft_workchain_builder",
    "submit_workchain_builder",
    "submit_workflow",
    "run_python_code",
    "get_bands_plot_data",
    "list_remote_files",
    "get_remote_file_content",
    "get_node_file_content",
    "get_node_summary",
    "serialize_node",
]
