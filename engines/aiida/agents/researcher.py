from pydantic_ai import Agent, RunContext
from src.sab_core.schema.response import SABRResponse
from engines.aiida.deps import AiiDADeps

# 1. Import your granular atomic tools from their specific categories
from engines.aiida.tools.base.node import load_node_summary
from engines.aiida.tools.process.process import get_process_state
from engines.aiida.tools.submission.submission import submit_standard_workchain
from engines.aiida.tools.cyclic.error_handler import diagnose_and_suggest_fix

# 2. Initialize the AiiDA-specialized Agent
# This agent stays inside the engines/ folder to keep sab_core clean.

SYSTEM_PROMPT = """
You are a proactive AiiDA Research Intelligence (SABR v2). 
Your mission is to provide high-level scientific insights and automate complex data exploration.

### SCIENTIFIC PHILOSOPHY
- ANALYZE & DISCOVER: Do not just output raw data. Look for patterns, anomalies, or physical trends in AiiDA nodes.
- PROACTIVE RETRY (CYCLIC LOGIC): If a tool execution fails or returns an error (e.g., convergence failure, missing pseudopotentials), do NOT simply report the error. Analyze the output, use your diagnostic tools, and attempt to fix the parameters to retry the task immediately.
- PROVENANCE AWARENESS: You understand the AiiDA directed acyclic graph (DAG). You can trace back from a Result to its Input structures.

### OPERATIONAL RULES
- ENVIRONMENT SYNC: You are running within a specific AiiDA profile/archive defined in your Context. Trust the data provided by your tools.
- TOOL FIRST: Use specific tools (list_groups, inspect_node, etc.) whenever possible.
- CODE POWER: If standard tools are insufficient for complex data mining, use the 'run_aiida_code' tool to write custom QueryBuilder scripts.

### SUGGESTION STRATEGY
- Always provide 2-3 "Smart Chips" (suggestions) in your response.
- Suggestions must be actionable next steps (e.g., "Analyze Band Structure", "Check Parent Calculation").
- Keep each suggestion under 5 words.

### SMART CHIP (SUGGESTION) STRATEGY:
1. AFTER DATA QUERY: Suggest inspecting a specific node or plotting data. 
   (e.g., "Inspect PK 101", "Plot Band Structure")
2. AFTER SUCCESSFUL SUBMISSION: Suggest monitoring the process or checking inputs.
   (e.g., "Monitor Workflow", "Verify K-Points")
3. AFTER FAILURE: Suggest a diagnostic action.
   (e.g., "Check Error Logs", "Refine Pseudo Potentials")
4. NO REPETITION: Do not suggest the task you just completed.

"""

aiida_researcher = Agent(
    'google-gla:gemini-1.5-flash',
    deps_type=AiiDADeps,
    result_type=SABRResponse,
    system_prompt=SYSTEM_PROMPT
)

# 3. Register Atomic Tools via Wrappers
# We wrap them to inject RunContext[AiiDADeps], ensuring environment awareness.

@aiida_researcher.tool
async def inspect_node(ctx: RunContext[AiiDADeps], pk: int) -> str:
    """
    Examine the details of a specific AiiDA node (Data or Calculation).
    """
    # Passing context to original logic if needed
    return await load_node_summary(pk)

@aiida_researcher.tool
async def monitor_process(ctx: RunContext[AiiDADeps], pk: int) -> str:
    """
    Check the current status and exit code of an active process.
    """
    return await get_process_state(pk)

@aiida_researcher.tool
async def submit_job(ctx: RunContext[AiiDADeps], structure_pk: int, workflow_type: str) -> str:
    """
    Submit a new simulation workchain to the AiiDA engine.
    """
    ctx.deps.log_step(f"Attempting to submit {workflow_type} for node {structure_pk}")
    return await submit_standard_workchain(structure_pk, workflow_type)

@aiida_researcher.tool
async def handle_execution_failure(ctx: RunContext[AiiDADeps], exit_status: int, log_snippet: str) -> str:
    """
    🚩 CYCLIC TOOL: Call this when a process FAILED to get a fix strategy.
    The agent will use the returned advice to adjust parameters and retry.
    """
    ctx.deps.log_step(f"Diagnosing failure for exit_status {exit_status}")
    fix_suggestion = await diagnose_and_suggest_fix(exit_status, log_snippet)
    return f"Diagnosis complete. Suggestion: {fix_suggestion}. You should now try to re-submit."