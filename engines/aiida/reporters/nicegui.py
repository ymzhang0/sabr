# examples/aiida/web/reporter.py
from sab_core.reporters.base import BaseReporter
from sab_core.schema.observation import Observation
from sab_core.schema.action import Action

class NiceGUIReporter(BaseReporter):
    def __init__(self, components):
        """
        传入我们在 web.py 中创建的 UI 组件字典
        """
        self.comp = components

    def emit(self, observation: Observation, action: Action) -> None:
        # 1. 更新右侧的 Schema 地图
        # 如果是 AiiDA 相关的扫描结果，更新到 debug 框
        if "aiida" in observation.source:
            self.comp['debug_log'].set_content(observation.raw)
        
        # 2. 在思考日志中打印当前的动作
        self.comp['thought_log'].push(f"👀 [Observed] {observation.source}")
        self.comp['thought_log'].push(f"🧠 [Decision] {action.name}: {action.payload}")
        
        # 3. 如果有 AI 的回复内容，可以在这里处理气泡更新
        # (假设 Action 的 payload 里包含要说的话)
        if action.name == "say":
            with self.comp['chat_area']:
                import nicegui.ui as ui
                ui.chat_message(action.payload, name='Agent', avatar='...')

    def report_thought(self, thought: str) -> None:
        # 专门用来显示 Gemini 的思考链 (Chain of Thought)
        self.comp['thought_log'].push(f"💭 {thought}")