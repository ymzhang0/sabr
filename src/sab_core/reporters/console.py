from loguru import logger
from sab_core.reporters.base import BaseReporter
from sab_core.schema.action import Action
from sab_core.schema.observation import Observation

class ConsoleReporter(BaseReporter):
    """继承自 BaseReporter，负责将步骤打印到终端"""
    def emit(self, observation: Observation, action: Action) -> None:
        logger.info("--- [SAB Step Report] ---")
        logger.info("Perceived from: {}", observation.source)
        # 截断太长的 raw 输出
        raw_snippet = observation.raw[:100] + "..." if len(observation.raw) > 100 else observation.raw
        logger.info("Raw: {}", raw_snippet)
        logger.info("Decision: {} {}", action.name, action.payload)
        logger.info("--------------------------")