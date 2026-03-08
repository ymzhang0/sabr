from dataclasses import dataclass

from src.aris_core.schema.action import Action
from src.aris_core.schema.observation import Observation


@dataclass
class UIState:
    cpu: float = 0.0
    action_name: str = "waiting..."
    message: str = "No messages yet."


class NiceGUIReporter:
    def __init__(self, state: UIState):
        self.state = state

    def emit(self, observation: Observation, action: Action) -> None:
        self.state.cpu = observation.features.get("cpu_usage", 0.0)
        self.state.action_name = action.name
        self.state.message = action.payload.get("message", "N/A")
