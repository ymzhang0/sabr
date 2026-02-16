from typing import Any
from engines.aiida.tools import process, profile, interpreter
from sab_core.schema.action import Action

class AiiDAExecutor:
    """
    通用执行器：将 Action 路由到对应的 Tool 函数。
    """
    def __init__(self):
        # 建立 动作名 -> 函数 的映射表
        self._tool_map = {
            "inspect_process": process.inspect_process,
            "list_groups": profile.list_groups,
            "get_statistics": profile.get_statistics,
            "switch_profile": profile.switch_profile,
            "run_aiida_code": interpreter.run_aiida_code, # 联动你的解释器
        }

    async def execute(self, action: Action) -> Any:
        """
        根据 Brain 给出的 Action，寻找对应的工具并执行。
        """
        if action.name == "say":
            # 如果是说话，直接返回内容
            return action.payload.get("content")

        if action.name in self._tool_map:
            tool_func = self._tool_map[action.name]
            # 执行工具（注意：如果工具是同步的，这里直接调用；如果是异步，加 await）
            try:
                # 这里的 **action.payload 会自动把 AI 给出的参数对号入座
                # 例如 AI 给出了 {"script": "print(1)"}, 则等同于 run_aiida_code(script="print(1)")
                result = tool_func(**action.payload)
                return result
            except Exception as e:
                return f"Execution Error in {action.name}: {str(e)}"

        return f"Unknown action: {action.name}"