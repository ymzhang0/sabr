from nicegui import ui

from src.aris_legacy.system_health.executor import ConsoleExecutor
from src.aris_legacy.system_health.perceptor import SystemPerceptor
from src.aris_legacy.system_health.web_reporter import NiceGUIReporter, UIState

app_state = UIState()
perceptor = SystemPerceptor()
executor = ConsoleExecutor()
reporter = NiceGUIReporter(app_state)


@ui.page("/")
def index():
    ui.label("ARIS System Monitor").classes("text-h4 q-mb-md")

    with ui.card().classes("w-64"):
        ui.label("System Status").classes("text-subtitle1")
        ui.label().bind_text_from(app_state, "cpu", lambda v: f"CPU Usage: {v:.1f}%")
        ui.linear_progress().bind_value_from(app_state, "cpu", lambda v: v / 100)

    with ui.card().classes("w-64 bg-grey-1"):
        ui.label("AI Decision").classes("text-subtitle1")
        ui.label().bind_text_from(app_state, "action_name", lambda v: f"Action: {v}")
        ui.label().bind_text_from(app_state, "message", lambda v: f"Info: {v}")

    def trigger_step():
        observation = perceptor.perceive()
        action = type("Action", (), {"name": "no_op", "payload": {"message": observation.raw}})()
        executor.execute(action)
        reporter.emit(observation, action)

    ui.button("Trigger Step", on_click=trigger_step).props("primary")


def run() -> None:
    ui.run(title="ARIS Dashboard", port=8080)


if __name__ in {"__main__", "__mp_main__"}:
    run()
