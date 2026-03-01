# src/sab_core/deps/base.py
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from loguru import logger

from src.sab_core.logging_utils import log_event
from src.sab_core.memory.json_memory import JSONMemory

@dataclass
class BaseSABRDeps:
    """Generic dependencies that every science agent needs."""
    memory: Optional[JSONMemory] = None
    current_step: int = 0
    max_steps: int = 10
    step_history: List[str] = field(default_factory=list)
    step_callback: Optional[Callable[[str], None]] = None

    def log_step(self, message: str):
        """Record agent execution steps for UI ticker and thought-log rendering."""
        self.step_history.append(message)
        logger.info(log_event("aiida.agent.step", step=message))
        callback = self.step_callback
        if callable(callback):
            try:
                callback(message)
            except Exception:  # noqa: BLE001
                logger.warning(log_event("aiida.agent.step.callback_failed", step=message))
