# src/sab_core/protocols/controller.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseController(ABC):
    """
    SAB 逻辑控制器基类
    职责：编排 Perceptor、Brain 和 Executor 的交互，并同步 UI 状态。
    """
    def __init__(self, engine: Any, components: Dict[str, Any]):
        self.engine = engine
        self.components = components

    @abstractmethod
    async def handle_send(self, text: Optional[str] = None):
        """处理用户发送消息的标准流程"""
        pass

    @abstractmethod
    async def switch_context(self, context_id: str):
        """处理上下文（环境/档案/Profile）切换的标准流程"""
        pass

    def update_ui_component(self, key: str, value: Any, method: str = "set_text"):
        """通用的 UI 更新辅助方法，增加一层抽象防止强耦合"""
        if key in self.components:
            component = self.components[key]
            if hasattr(component, method):
                getattr(component, method)(value)