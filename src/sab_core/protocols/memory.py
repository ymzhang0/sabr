# src/sab_core/protocols/memory.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseMemory(ABC):
    """
    SABRM 架构中的 M (Memory) 协议
    负责对话历史、决策路径及环境快照的持久化与检索
    """
    @abstractmethod
    def store(self, turn_data: Dict[str, Any]):
        """存储一个回合的数据（包含 Observation, Intent, Action, Response）"""
        pass

    @abstractmethod
    def get_context(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取用于 Brain 决策的上下文历史"""
        pass

    @abstractmethod
    def clear(self):
        """清空记忆"""
        pass