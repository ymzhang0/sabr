# engines/aiida/executors/executor.py

import asyncio
from typing import Any
from loguru import logger
from sab_core.schema.action import Action

# 批量导入你的工具库
from engines.aiida.tools import (
    profile, calculation, process, group, 
    submission, remote, repository, bands, interpreter
)

class AiiDAExecutor:
    def __init__(self):
        # 建立一个完整的工具清单
        self.tool_map = {
            # 1. 环境与统计 (Profile/Group)
            "get_statistics": profile.get_statistics,
            "list_groups": profile.list_groups,
            "inspect_group": group.inspect_group,
            
            # 2. 深度诊断 (Process/Calculation)
            "inspect_process": process.inspect_process,
            "get_calculation_io": calculation.get_calculation_io,
            "get_process_log": process.get_process_log,
            
            # 3. 数据提取 (Bands/Remote/Repo)
            "get_bands_plot_data": bands.get_bands_plot_data,
            "list_remote_files": remote.list_remote_files,
            "get_node_file_content": repository.get_node_file_content,
            
            # 4. 任务提交 (Submission)
            "inspect_workchain": submission.inspect_workchain,
            "submit_draft": submission.submit_draft,
            
            # 5. 兜底方案：动态执行
            "run_python_code": interpreter.run_python_code,
        }

    async def execute(self, action: Action) -> Any:
        if action.name == "say": return None

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