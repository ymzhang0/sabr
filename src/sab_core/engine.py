from typing import Any, Optional
from sab_core.protocols.brain import Brain
from sab_core.protocols.executor import Executor
from sab_core.protocols.perception import Perceptor
from sab_core.reporters.base import BaseReporter

class SABEngine:
    def __init__(
        self,
        perceptor: Perceptor,
        brain: Brain,
        executor: Executor,
        reporters: list[BaseReporter] | None = None,
    ) -> None:
        self._perceptor = perceptor
        self._brain = brain
        self._executor = executor
        self._reporters = list(reporters) if reporters else []

    async def run_once(self, intent: Optional[str] = None) -> Any:
        observation = self._perceptor.perceive(intent=intent)
        # 注意这里的 await！
        action = await self._brain.decide(observation) 
        
        for reporter in self._reporters:
            reporter.emit(observation, action)
        
        # 执行器也建议异步化
        return await self._executor.execute(action)