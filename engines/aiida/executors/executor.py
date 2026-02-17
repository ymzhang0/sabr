# engines/aiida/executors/executor.py

import asyncio
from typing import Any
from loguru import logger
from sab_core.schema.action import Action

# 批量导入你的工具库
from engines.aiida import tools

class AiiDAExecutor:
    def __init__(self):
        # 建立一个完整的工具清单
        self.tool_map =  {name: getattr(tools, name) for name in tools.__all__}

    async def execute(self, action: Action) -> Any:
        if action.name == "say": return None
        # 🚩 改进处理：专门捕获并记录系统错误，但不抛出“未知工具”警告
        if action.name == "error_reported":
            error_msg = action.payload.get('message', 'Unknown brain error')
            logger.error(f"🧠 Brain Report Error: {error_msg}")
            return f"System Error: {error_msg}" # 返回给 Reporter 展示
            
        tool_func = self.tool_map.get(action.name)
        if not tool_func:
            logger.warning(f"⚠️ Action '{action.name}' is not registered in Executor.")
            return f"Error: Tool {action.name} not found."

        logger.info(f"🛠️ Tool Calling: {action.name}")
        
        try:
            # 建议使用 asyncio.to_thread 运行同步的 AiiDA 查询，避免阻塞 UI
            result = await asyncio.to_thread(tool_func, **action.payload)
            return result
        except Exception as e:
            return f"Execution Error: {str(e)}"