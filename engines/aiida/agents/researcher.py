from typing import Any

from pydantic_ai import Agent, RunContext
from src.sab_core.schema.response import SABRResponse
from engines.aiida.deps import AiiDADeps
from aiida.manage.configuration import get_config

# 1. Import tools aligned with `tools/__init__.py::__all__`.
from engines.aiida.tools import (
    list_system_profiles,
    list_local_archives,
    switch_profile,
    get_statistics,
    list_groups,
    get_unified_source_map,
    get_database_summary,
    inspect_group,
    inspect_process,
    fetch_recent_processes,
    inspect_workchain_spec,
    draft_workchain_builder,
    submit_workchain_builder,
    run_python_code,
    get_bands_plot_data,
    list_remote_files,
    get_remote_file_content,
    get_node_file_content
)
# Import node summary helper for detailed node inspection.
from engines.aiida.tools.base.node import get_node_summary

    
# 2. Define the enhanced system prompt.
SYSTEM_PROMPT = """
You are a proactive AiiDA Research Intelligence (SABR v2). 
Your mission is to provide high-level scientific insights and automate complex data exploration.

### OPERATIONAL RULES
- ENVIRONMENT SYNC: You are inside the archive/profile defined in Context. Trust the tools.
- CYCLIC RETRY: If a calculation fails, use 'inspect_process' to read logs, diagnose, and retry with new parameters.
- SUGGESTIONS: Always provide 2-3 "Smart Chips" (suggestions) under 5 words in your response.

### TOOLBOX USAGE
- DB Analysis: Use 'get_database_statistics' and 'list_groups' to navigate.
- Deep Dive: Use 'inspect_group' to see attributes of many nodes, or 'inspect_node' for one.
- Submission: Always 'inspect_workchain_spec' before drafting a builder to ensure inputs are correct.
- Custom Logic: If standard tools fail, write custom QueryBuilder code using 'run_aiida_code'.
"""

aiida_researcher = Agent(
    'google-gla:gemini-1.5-flash',
    deps_type=AiiDADeps,
    output_type=SABRResponse,
    system_prompt=SYSTEM_PROMPT,
    retries=3
)


def _format_context_node_line(node: dict[str, Any]) -> str:
    pk = node.get("pk", "?")
    error = node.get("error")
    if error:
        return f"- PK {pk}: unavailable ({error})"

    details = [
        f"PK {pk}",
        f"type={node.get('node_type') or 'Unknown'}",
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

 
# --- 3. Register tools (kept in sync with tools/__init__.py) ---

# --- Profile & System Management ---
@aiida_researcher.tool
async def list_profiles(ctx: RunContext[AiiDADeps]):
    """List all available AiiDA profiles on this system."""
    profiles = list_system_profiles()
    config = get_config()
    default_name = config.default_profile_name

    # Serialize Profile objects to plain dict for model/tool transport.
    if isinstance(profiles, dict):
        values = profiles.values()
    else:
        values = profiles

    result = []
    for p in values:
        name = getattr(p, "name", str(p))
        result.append(
            {
                "name": name,
                "is_default": bool(default_name and name == default_name),
            }
        )
    return result

@aiida_researcher.tool
async def list_archives(ctx: RunContext[AiiDADeps]):
    """List .aiida or .zip archive files in the current directory."""
    return list_local_archives()

@aiida_researcher.tool
async def switch_aiida_profile(ctx: RunContext[AiiDADeps], profile_name: str):
    """Switch the current active AiiDA profile."""
    ctx.deps.log_step(f"Switching to profile: {profile_name}")
    return switch_profile(profile_name)

@aiida_researcher.tool
async def get_db_statistics(ctx: RunContext[AiiDADeps]):
    """Get high-level counts of nodes and processes in the current database."""
    return get_statistics()

@aiida_researcher.tool
async def get_db_summary(ctx: RunContext[AiiDADeps]):
    """Get a quick summary of database health (node count, failed processes)."""
    return get_database_summary()

@aiida_researcher.tool
async def get_source_map(ctx: RunContext[AiiDADeps], target: str):
    """Get a unified map of groups for a specific profile or archive."""
    return get_unified_source_map(target)

# --- Groups & Nodes ---
@aiida_researcher.tool
async def list_aiida_groups(ctx: RunContext[AiiDADeps], search_string: str = None):
    """List all groups, optionally filtered by name."""
    return list_groups(search_string)

@aiida_researcher.tool
async def inspect_aiida_group(ctx: RunContext[AiiDADeps], group_name: str, limit: int = 20):
    """Deeply analyze all nodes in a group (attributes & extras)."""
    ctx.deps.log_step(f"Analyzing group: {group_name}")
    return inspect_group(group_name, limit)

@aiida_researcher.tool
async def inspect_node_details(ctx: RunContext[AiiDADeps], pk: int):
    """Get a structured summary of a specific node's type, state, and attributes."""
    return get_node_summary(pk)

# --- Process & Submission ---
@aiida_researcher.tool
async def inspect_process_details(ctx: RunContext[AiiDADeps], identifier: str):
    """Analyze a process (calculation or workchain), including logs and exit status."""
    ctx.deps.log_step(f"Inspecting process logs: {identifier}")
    return inspect_process(identifier)

@aiida_researcher.tool
async def get_recent_aiida_processes(ctx: RunContext[AiiDADeps], limit: int = 15):
    """Fetch the most recent processes for status overview."""
    return fetch_recent_processes(limit)

@aiida_researcher.tool
async def check_workflow_spec(ctx: RunContext[AiiDADeps], entry_point: str):
    """Inspect the required inputs and protocols for a WorkChain."""
    return inspect_workchain_spec(entry_point)

@aiida_researcher.tool
async def submit_new_workflow(ctx: RunContext[AiiDADeps], workchain: str, structure_pk: int, code: str, protocol: str = 'moderate'):
    """Draft and submit a new workchain using specified protocols."""
    ctx.deps.log_step(f"Submitting workflow: {workchain}")
    draft = draft_workchain_builder(workchain, structure_pk, code, protocol)
    if isinstance(draft, dict) and draft.get("status") == "DRAFT_READY":
        return submit_workchain_builder(draft)
    return f"Failed to submit: {draft}"

# --- Data & Visualization ---
@aiida_researcher.tool
async def get_bands_data(ctx: RunContext[AiiDADeps], pk: int):
    """Retrieve plot-ready data for Band Structure nodes."""
    return get_bands_plot_data(pk)

@aiida_researcher.tool
async def list_remote_path_files(ctx: RunContext[AiiDADeps], remote_path_pk: int):
    """List files in a RemoteData directory on the cluster."""
    return list_remote_files(remote_path_pk)

@aiida_researcher.tool
async def get_remote_file(ctx: RunContext[AiiDADeps], remote_path_pk: int, filename: str):
    """Read the content of a file from a remote directory."""
    return get_remote_file_content(remote_path_pk, filename)

@aiida_researcher.tool
async def get_node_file(ctx: RunContext[AiiDADeps], pk: int, filename: str):
    """Read the content of a file stored in a node's repository."""
    return get_node_file_content(pk, filename)

# --- Advanced Logic ---
@aiida_researcher.tool
async def run_aiida_code_script(ctx: RunContext[AiiDADeps], script: str):
    """Execute custom Python/AiiDA code for complex data mining."""
    ctx.deps.log_step("Running custom research script")
    return run_python_code(script)
