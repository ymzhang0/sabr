# engines/aiida/executors/executor.py

import asyncio
from typing import Any
from loguru import logger
from sab_core.schema.action import Action
import inspect
# 批量导入你的工具库
from engines.aiida import tools

class AiiDAExecutor:
    def __init__(self):
        # 建立一个完整的工具清单
        self.tool_map =  {name: getattr(tools, name) for name in tools.__all__}

    async def execute(self, action: Action) -> Any:
        """
        Execute the specified action with automatic argument filtering.
        This prevents 'unexpected keyword argument' errors from redundant LLM output.
        """
        # 1. Skip if it's just a conversation action
        if action.name == "say": 
            return None

        # 2. Handle specific error reports from the Brain
        if action.name == "error_reported":
            error_msg = action.payload.get('message', 'Unknown brain error')
            logger.error(f"🧠 Brain Report Error: {error_msg}")
            return f"System Error: {error_msg}" # 返回给 Reporter 展示
        
        # 3. Retrieve the target tool function
        tool_func = self.tool_map.get(action.name)
        if not tool_func:
            logger.warning(f"⚠️ Action '{action.name}' is not registered in Executor.")
            return f"Error: Tool {action.name} not found."
        
        # 🚩 4. Argument Filtering Logic
        # Introspect the function signature to determine valid parameters
        sig = inspect.signature(tool_func)
        parameters = sig.parameters
        
        # Check if the function accepts variadic keyword arguments (**kwargs)
        accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values())
        
        if accepts_kwargs:
            # If the tool accepts **kwargs, we only filter out known "meta" keys 
            # added by the Brain/Engine to avoid polluting the tool logic.
            filtered_payload = {
                k: v for k, v in action.payload.items() 
                if k not in ['content', 'suggestions']
            }
        else:
            # Strict filtering: keep only parameters explicitly defined in the function signature
            filtered_payload = {
                k: v for k, v in action.payload.items() 
                if k in parameters
            }
        logger.info(f"🛠️ Tool Calling: {action.name}")
        
        try:
            # 5. Execute the tool function
            # Use asyncio.to_thread for synchronous AiiDA DB calls to keep the UI responsive
            result = await asyncio.to_thread(tool_func, **filtered_payload)
            return result
        except Exception as e:
            logger.exception(f"Exception during execution of {action.name}")
            return f"Execution Error: {str(e)}"