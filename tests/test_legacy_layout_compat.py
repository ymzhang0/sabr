from __future__ import annotations

from pathlib import Path

from src.aris_core.config import settings
from src.aris_apps.aiida import specializations
from src.aris_legacy.system_health.executor import ConsoleExecutor
from src.aris_legacy.system_health.perceptor import SystemPerceptor
from src.aris_legacy.system_health.web_reporter import NiceGUIReporter, UIState


def test_new_config_layout_is_default() -> None:
    assert settings.ARIS_PRESETS_FILE.endswith("config/apps/aiida/presets.yaml")
    assert settings.ARIS_AIIDA_SETTINGS_FILE.endswith("config/apps/aiida/settings.yaml")
    assert Path(settings.ARIS_AIIDA_SPECIALIZATIONS_ROOT).as_posix().endswith(
        "config/apps/aiida/specializations"
    )
    assert specializations.SPECIALIZATIONS_ROOT.as_posix().endswith("config/apps/aiida/specializations")


def test_system_health_legacy_package_imports() -> None:
    state = UIState()
    reporter = NiceGUIReporter(state)
    perceptor = SystemPerceptor()
    executor = ConsoleExecutor()

    observation = perceptor.perceive()
    action = type("Action", (), {"name": "no_op", "payload": {"message": observation.raw}})()
    assert executor.execute(action) is True
    reporter.emit(observation, action)
    assert state.message == observation.raw
