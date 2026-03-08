from __future__ import annotations

from pathlib import Path

from src.aris_core.config import settings
from src.aris_legacy.nicegui import THEMES as legacy_themes
from src.aris_legacy.nicegui import create_aiida_layout as legacy_layout
from src.sab_engines.aiida import specializations
from src.sab_engines.aiida.ui.legacy_nicegui import THEMES as shim_themes
from src.sab_engines.aiida.ui.legacy_nicegui import create_aiida_layout as shim_layout
from src.sab_engines.system_health.executor import ConsoleExecutor
from src.sab_engines.system_health.perceptor import SystemPerceptor
from src.sab_engines.system_health.web_reporter import NiceGUIReporter, UIState


def test_new_config_layout_is_default() -> None:
    assert settings.ARIS_PRESETS_FILE.endswith("config/apps/aiida/presets.yaml")
    assert settings.ARIS_AIIDA_SETTINGS_FILE.endswith("config/apps/aiida/settings.yaml")
    assert settings.SABR_PRESETS_FILE == settings.ARIS_PRESETS_FILE
    assert settings.SABR_AIIDA_SETTINGS_FILE == settings.ARIS_AIIDA_SETTINGS_FILE
    assert Path(settings.ARIS_AIIDA_SPECIALIZATIONS_ROOT).as_posix().endswith(
        "config/apps/aiida/specializations"
    )
    assert specializations.SPECIALIZATIONS_ROOT.as_posix().endswith("config/apps/aiida/specializations")


def test_legacy_nicegui_wrappers_point_to_new_legacy_package() -> None:
    assert shim_themes is legacy_themes
    assert shim_layout is legacy_layout


def test_legacy_system_health_wrappers_import() -> None:
    state = UIState()
    reporter = NiceGUIReporter(state)
    perceptor = SystemPerceptor()
    executor = ConsoleExecutor()

    observation = perceptor.perceive()
    action = type("Action", (), {"name": "no_op", "payload": {"message": observation.raw}})()
    assert executor.execute(action) is True
    reporter.emit(observation, action)
    assert state.message == observation.raw
