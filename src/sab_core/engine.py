# src/sab_core/engine.py (核心升级)
from sab_core.protocols.perception import Perceptor
from sab_core.protocols.brain import Brain
from sab_core.protocols.executor import Executor
from sab_core.protocols.reporter import Reporter
from sab_core.protocols.memory import Memory
from sab_core.schema.observation import Observation # 🚩 确保导入了这个类
from typing import List

class SABEngine:
    def __init__(
        self, 
        perceptor: Perceptor, 
        brain: Brain,
        executor:Executor, 
        reporters:List[Reporter]=[], 
        memory:Memory=None
        ):

        self._perceptor = perceptor
        self._brain = brain
        self._executor = executor
        self._reporters = reporters
        self._memory = memory  # 🚩 新增 Memory 组件

    def log(self, message: str, level: str = "INFO"):
        """将调试信息广播给所有绑定的 Reporter"""
        for reporter in self._reporters:
            if hasattr(reporter, 'debug'):
                reporter.debug('> ' + message, level)

    async def run_once(self, intent: str):
        # 1. S (Perceive)
        self.log("Step 1: Perceiving...", level="DEBUG")
        observation = self._perceptor.perceive(intent)
        
        # 2. M (Retrieve) - 注入对话历史 + 操作历史
        history = self._memory.get_context() if self._memory else []
        action_logs = self._memory.get_action_history() if self._memory else ""
        
        # 🚩 技巧：将操作日志作为“系统提示”的一部分临时注入观察结果，帮助 Brain 反思
        enhanced_observation = Observation(
            source=observation.source,
            raw=observation.raw + "\n\n" + action_logs
        )
        
        # 3. B (Decide)
        self.log("Step 2: Deciding with Brain...", level="DEBUG")
        action = await self._brain.decide(enhanced_observation, history=history)     
        self.log(f"Step 3: Action defined -> {action.name}", level="DEBUG")
           
        # 4. A (Execute)
        # 假设 executor 会返回一个包含执行细节的 Result 对象
        result = await self._executor.execute(action)        
        response_package = {
            "result": result, # 工具执行的原始结果
            "content": action.payload.get("content", ""), # AI 说的话
            "suggestions": action.payload.get("suggestions", []), # 🚩 建议卡片列表
            "action_name": action.name
        }
        # 5. M (Store) - 🚩 记录全量信息
        if self._memory:
            self._memory.store({
                "intent": intent,
                "actions": [{
                    "command": action.payload.get("command") or action.name,
                    "success": getattr(result, 'success', True),
                    "output_summary": str(result)[:100]
                }],
                "response": response_package["content"] if action.name == "say" else "Action Executed",
            })
        # 6. Report (R)
        for reporter in self._reporters:
            reporter.emit(observation, action)
            
        return response_package # 🚩 返回打包后的数据