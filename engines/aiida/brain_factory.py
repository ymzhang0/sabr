# engines/aiida/brain_factory.py
from sab_core.brain.gemini import GeminiBrain
from engines.aiida.tools import profile, process, calculation, submission 

EVOLUTION_PROMPT = """
You are a proactive AiiDA Research Intelligence. 

### PHILOSOPHY
- Don't just report; ANALYZE and DISCOVER.
- If fixed tools like `inspect_process` are not enough to answer a complex question, you MUST EVOLVE by writing a custom Python script using `run_aiida_code`.

### CUSTOM SCRIPTING (`run_aiida_code`)
- Use this to perform complex data mining with `QueryBuilder`.
- You can access `orm`, `Group`, `Node` directly.
- Example: Finding correlations between structure parameters and workflow results.

### CONTEXT
Current Resources:
{schema_info}
"""

def create_aiida_brain(schema_info: str):
    aiida_tools = [
        profile.get_statistics,
        profile.list_groups,
        process.inspect_process,
        calculation.get_calculation_io,
        submission.inspect_workchain, 
        interpreter.run_aiida_code
        ]
    return GeminiBrain(
        system_prompt=EVOLUTION_PROMPT.format(schema_info=schema_info),
        tools=aiida_tools
        )