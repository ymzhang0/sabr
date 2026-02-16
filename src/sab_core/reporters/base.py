# src/sab_core/reporters/base.py
from abc import ABC, abstractmethod
from sab_core.schema.observation import Observation
from sab_core.schema.action import Action

class BaseReporter(ABC):
    """
    SAB 报告器基类。
    所有的报告器（Console, Web, etc.）都应该继承它。
    """
    
    @abstractmethod
    def emit(self, observation: Observation, action: Action) -> None:
        """核心方法：负责将一次 观察-决策 循环输出到目的地"""
        pass

    def report_error(self, message: str) -> None:
        """通用方法：报告系统错误"""
        print(f"ERROR: {message}")

    def report_thought(self, thought: str) -> None:
        """通用方法：报告大脑的中间思考过程"""
        pass