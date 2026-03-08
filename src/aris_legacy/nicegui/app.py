from nicegui import app, ui

from src.aris_apps.aiida.paths import static_dir
from src.aris_core.config import settings
from src.aris_core.memory import JSONMemory
from src.aris_legacy.nicegui.controller import RemoteAiiDAController
from src.aris_legacy.nicegui.layout import create_aiida_layout

API_URL = "http://localhost:8000"
global_memory = JSONMemory(namespace="aiida_v2_ui")

app.add_static_files("/aiida/static", str(static_dir()))


@ui.page("/")
async def main():
    available_models = [settings.DEFAULT_MODEL]
    components = create_aiida_layout(theme_name="gemini_dark", available_models=available_models)

    ctrl = RemoteAiiDAController(api_url=API_URL, components=components, memory=global_memory)

    components["send_btn"].on("click", lambda: ctrl.handle_send())
    components["input"].on("keydown.enter", lambda: ctrl.handle_send())
    components["upload_btn"].on("click", ctrl.pick_local_file)
    components["archive_select"].on_value_change(lambda e: ctrl.switch_context(e.value))

    for card, intent in components["suggestion_cards"]:
        card.on("click", lambda i=intent: ctrl.handle_send(preset_text=i))

    components["model_select"].on_value_change(lambda e: ui.notify(f"Brain switched to: {e.value}", type="info"))
    ui.on("node_clicked", lambda msg: ctrl.handle_node_inspection(msg))

    with components["archive_history"]:
        ctrl._load_archive_history()

    app.on_shutdown(ctrl.close)


def run() -> None:
    ui.run(
        port=8080,
        title="ARIS | AiiDA Assistant",
        dark=True,
        reload=True,
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
