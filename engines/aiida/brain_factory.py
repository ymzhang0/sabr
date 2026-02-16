# engines/aiida/brain_factory.py
from sab_core.brain.gemini import GeminiBrain
from engines.aiida.tools.process import inspect_process
from engines.aiida.tools.interpreter import run_aiida_code
from engines.aiida.tools.profile import list_groups, get_statistics

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
    return GeminiBrain(
        system_prompt=EVOLUTION_PROMPT.format(schema_info=schema_info),
        tools=[inspect_process, list_groups, get_statistics, run_aiida_code]
    )