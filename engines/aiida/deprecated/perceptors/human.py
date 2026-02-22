from sab_core.schema.observation import Observation

class HumanPerceptor:
    """捕获用户在网页输入框中的对话意图"""
    def __init__(self):
        self.current_input = ""

    def set_input(self, text: str):
        self.current_input = text

    def perceive(self) -> Observation:
        return Observation(
            source="user_input",
            features={"text": self.current_input},
            raw=f"User says: {self.current_input}"
        )