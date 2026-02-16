from dataclasses import dataclass
from sab_core.schema.action import Action
from sab_core.schema.observation import Observation

@dataclass
class UIState:
    """响应式数据模型"""
    cpu: float = 0.0
    action_name: str = "waiting..."
    message: str = "No messages yet."

class NiceGUIReporter:
    def __init__(self, state: UIState):
        self.state = state

    def emit(self, observation: Observation, action: Action) -> None:
        # 直接更新对象属性，UI 会通过绑定自动刷新
        self.state.cpu = observation.features.get("cpu_usage", 0.0)
        self.state.action_name = action.name
        self.state.message = action.payload.get("message", "N/A")