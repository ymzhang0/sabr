# src/sab_core/deps/base.py
from dataclasses import dataclass, field
from typing import Optional, List, Any
from src.sab_core.memory.json_memory import JSONMemory

@dataclass
class BaseSABRDeps:
    """Generic dependencies that every science agent needs."""
    memory: Optional[JSONMemory] = None
    current_step: int = 0
    max_steps: int = 10
    step_history: List[str] = field(default_factory=list)

    def log_step(self, message: str):
        """记录 Agent 的执行步骤，用于前端 Ticker 和 Thought Log"""
        self.step_history.append(message)
        print(f"⚙️ [Step]: {message}")