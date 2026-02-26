from typing import Any

from pydantic_ai import Agent, RunContext

from engines.aiida.deps import AiiDADeps
from engines.aiida.tools import (
    draft_workchain_builder,
    fetch_recent_processes,
    get_bands_plot_data,
    get_database_summary,
    get_node_file_content,
    get_node_summary,
    get_remote_file_content,
    get_remote_workchain_spec as get_remote_workchain_spec_via_bridge,
    get_statistics,
    get_unified_source_map,
    inspect_group,
    inspect_lab_infrastructure as inspect_lab_infrastructure_via_bridge,
    inspect_process,
    inspect_workchain_spec,
    list_groups,
    list_local_archives,
    list_remote_files,
    list_remote_plugins as list_remote_plugins_via_bridge,
    list_system_profiles,
    run_python_code,
    submit_workflow,
    switch_profile,
)
from src.sab_core.schema.response import SABRResponse

SYSTEM_PROMPT = """
You are a proactive AiiDA Research Intelligence (SABR v2).
Your mission is to provide high-level scientific insights and automate complex data exploration.

### OPERATIONAL RULES
- ENVIRONMENT SYNC: The aiida-worker bridge is the source of truth for profile, resources, and workflow metadata.
- CYCLIC RETRY: If a calculation fails, use 'inspect_process' to read logs, diagnose, and retry with new parameters.
- SUGGESTIONS: Always provide 2-3 "Smart Chips" (suggestions) under 5 words in your response.

### TOOLBOX USAGE
- DB Analysis: Use 'get_database_statistics' and 'list_groups' to navigate.
- Deep Dive: Use 'inspect_group' to see attributes of many nodes, or 'inspect_node' for one.
- Available WorkChains: When asked about plugins/workchains, call 'list_remote_plugins' first; this is the source of truth from the active worker bridge.
- WorkChain Spec: Use 'get_remote_workchain_spec' (or 'check_workflow_spec') before drafting a builder.
- Submission readiness: call 'inspect_lab_infrastructure' before submission to confirm required computers/codes exist.
- Custom Logic: If standard tools fail, use 'run_aiida_code' to execute targeted worker-side scripts.
"""

aiida_researcher = Agent(
    "google-gla:gemini-1.5-flash",
    deps_type=AiiDADeps,
    output_type=SABRResponse,
    system_prompt=SYSTEM_PROMPT,
    retries=3,
)


def _format_context_node_line(node: dict[str, Any]) -> str:
    pk = node.get("pk", "?")
    error = node.get("error")
    if error:
        return f"- PK {pk}: unavailable ({error})"

    details = [
        f"PK {pk}",
        f"type={node.get('node_type') or node.get('type') or 'Unknown'}",
        f"label={node.get('label') or 'N/A'}",
    ]
    if node.get("formula"):
        details.append(f"formula={node['formula']}")
    if node.get("process_state"):
        details.append(f"process_state={node['process_state']}")
    if node.get("ctime"):
        details.append(f"ctime={node['ctime']}")
    return "- " + " | ".join(details)


@aiida_researcher.system_prompt(dynamic=True)
def add_referenced_nodes_prompt(ctx: RunContext[AiiDADeps]) -> str:
    context_nodes = getattr(ctx.deps, "context_nodes", None) or []
    if not context_nodes:
        return ""

    max_items = 12
    lines = [
        "### REFERENCED AiiDA NODES",
        "Treat these user-selected nodes as first-class context for this turn:",
    ]
    for node in context_nodes[:max_items]:
        lines.append(_format_context_node_line(node))
    if len(context_nodes) > max_items:
        lines.append(f"- ... {len(context_nodes) - max_items} more referenced nodes omitted.")
    return "\n".join(lines)


@aiida_researcher.tool
async def list_profiles(ctx: RunContext[AiiDADeps]):
    """List all configured profiles known by the active worker bridge."""
    payload = await list_system_profiles()
    if isinstance(payload, str):
        return {"error": payload}

    if isinstance(payload, dict):
        profiles = payload.get("profiles")
        if isinstance(profiles, list):
            return profiles
        return payload

    return payload


@aiida_researcher.tool
async def list_archives(ctx: RunContext[AiiDADeps]):
    """List `.aiida`/`.zip` archives visible to the worker."""
    return await list_local_archives()


@aiida_researcher.tool
async def switch_aiida_profile(ctx: RunContext[AiiDADeps], profile_name: str):
    """Switch active worker profile."""
    ctx.deps.log_step(f"Switching to profile: {profile_name}")
    return await switch_profile(profile_name)


@aiida_researcher.tool
async def get_db_statistics(ctx: RunContext[AiiDADeps]):
    """Get high-level infra/database counts from worker statistics endpoint."""
    return await get_statistics()


@aiida_researcher.tool
async def get_db_summary(ctx: RunContext[AiiDADeps]):
    """Get compact database health summary."""
    return await get_database_summary()


@aiida_researcher.tool
async def get_source_map(ctx: RunContext[AiiDADeps], target: str):
    """Get unified profile/archive group map from worker."""
    return await get_unified_source_map(target)


@aiida_researcher.tool
async def list_aiida_groups(ctx: RunContext[AiiDADeps], search_string: str = None):
    """List groups, optionally filtered by substring."""
    return await list_groups(search_string)


@aiida_researcher.tool
async def inspect_aiida_group(ctx: RunContext[AiiDADeps], group_name: str, limit: int = 20):
    """Inspect one group with node attributes/extras."""
    ctx.deps.log_step(f"Analyzing group: {group_name}")
    return await inspect_group(group_name, limit)


@aiida_researcher.tool
async def inspect_node_details(ctx: RunContext[AiiDADeps], pk: int):
    """Get structured node summary by PK."""
    return await get_node_summary(pk)


@aiida_researcher.tool
async def list_remote_plugins(ctx: RunContext[AiiDADeps]):
    """Source of truth for available WorkChains from worker bridge."""
    ctx.deps.log_step("Fetching remote plugin list from worker bridge")
    return await list_remote_plugins_via_bridge()


@aiida_researcher.tool
async def inspect_lab_infrastructure(ctx: RunContext[AiiDADeps]):
    """Inspect remote infrastructure (profile/daemon/computers/codes) before submission."""
    ctx.deps.log_step("Inspecting lab infrastructure from worker bridge")
    return await inspect_lab_infrastructure_via_bridge()


@aiida_researcher.tool
async def get_remote_workchain_spec(ctx: RunContext[AiiDADeps], entry_point: str):
    """Read WorkChain spec from worker bridge."""
    ctx.deps.log_step(f"Fetching remote WorkChain spec: {entry_point}")
    return await get_remote_workchain_spec_via_bridge(entry_point)


@aiida_researcher.tool
async def inspect_process_details(ctx: RunContext[AiiDADeps], identifier: str):
    """Inspect process summary/logs/provenance by PK/UUID."""
    ctx.deps.log_step(f"Inspecting process logs: {identifier}")
    return await inspect_process(identifier)


@aiida_researcher.tool
async def get_recent_aiida_processes(ctx: RunContext[AiiDADeps], limit: int = 15):
    """Fetch recent processes for status overview."""
    return await fetch_recent_processes(limit)


@aiida_researcher.tool
async def check_workflow_spec(ctx: RunContext[AiiDADeps], entry_point: str):
    """Inspect WorkChain inputs via worker spec endpoint."""
    return await inspect_workchain_spec(entry_point)


@aiida_researcher.tool
async def submit_new_workflow(
    ctx: RunContext[AiiDADeps],
    workchain: str,
    structure_pk: int,
    code: str,
    protocol: str = "moderate",
):
    """Draft and submit a new WorkChain through worker-side builder endpoints."""
    ctx.deps.log_step(f"Submitting workflow: {workchain}")
    draft = await draft_workchain_builder(workchain, structure_pk, code, protocol)
    if isinstance(draft, dict) and draft.get("status") == "DRAFT_READY":
        return await submit_workflow(draft)
    return {"error": "Failed to draft workflow", "details": draft}


@aiida_researcher.tool
async def get_bands_data(ctx: RunContext[AiiDADeps], pk: int):
    """Retrieve plot-ready bands payload by node PK."""
    return await get_bands_plot_data(pk)


@aiida_researcher.tool
async def list_remote_path_files(ctx: RunContext[AiiDADeps], remote_path_pk: int):
    """List files in a RemoteData directory."""
    return await list_remote_files(remote_path_pk)


@aiida_researcher.tool
async def get_remote_file(ctx: RunContext[AiiDADeps], remote_path_pk: int, filename: str):
    """Read file content from RemoteData."""
    return await get_remote_file_content(remote_path_pk, filename)


@aiida_researcher.tool
async def get_node_file(ctx: RunContext[AiiDADeps], pk: int, filename: str):
    """Read file content from node repository/folder data."""
    return await get_node_file_content(pk, filename)


@aiida_researcher.tool
async def run_aiida_code_script(ctx: RunContext[AiiDADeps], script: str):
    """Execute targeted Python/AiiDA code on the worker."""
    ctx.deps.log_step("Running custom research script on worker")
    return await run_python_code(script)
