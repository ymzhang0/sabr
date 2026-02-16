from nicegui import ui
from sab_core import GeminiBrain, SABEngine
from sab_core.reporters import ConsoleReporter

from perceptor import SystemPerceptor
from executor import ConsoleExecutor
from web_reporter import NiceGUIReporter, UIState

# 全局状态和引擎（保证整个 App 生命周期内只有一个 Agent 在跑）
app_state = UIState()
engine = SABEngine(
        perceptor=SystemPerceptor(),
        brain=GeminiBrain(),
        executor=ConsoleExecutor(),
        reporters=[
            ConsoleReporter(), 
            NiceGUIReporter(app_state)
        ]
    )

@ui.page("/")
def index():
    ui.label("SAB System Monitor").classes("text-h4 q-mb-md")
    
    with ui.card().classes("w-64"):
        ui.label("System Status").classes("text-subtitle1")
        # 核心：使用 bind_text 直接绑定对象属性
        ui.label().bind_text_from(app_state, "cpu", lambda v: f"CPU Usage: {v:.1f}%")
        ui.linear_progress().bind_value_from(app_state, "cpu", lambda v: v/100)

    with ui.card().classes("w-64 bg-grey-1"):
        ui.label("AI Decision").classes("text-subtitle1")
        ui.label().bind_text_from(app_state, "action_name", lambda v: f"Action: {v}")
        ui.label().bind_text_from(app_state, "message", lambda v: f"Info: {v}")

    ui.button("Trigger Step", on_click=engine.run_once).props("primary")

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="SAB Dashboard", port=8080)