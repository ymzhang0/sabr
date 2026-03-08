from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("GOOGLE_API_KEY", "dummy")

from src.aris_apps.aiida.agent.researcher import aiida_researcher
from src.aris_apps.aiida.api.router import router as aiida_router
from src.aris_apps.aiida.chat import get_chat_snapshot
from src.aris_apps.aiida.client import get_aiida_worker_client
from src import aris_core
from src.aris_core.config import Settings, settings
from src.aris_core.deps import BaseARISDeps
from src.aris_core.memory import ARISMemoryState, JSONMemory
from src.aris_core.protocols import Executor, Perceptor
from src.aris_core.schema import ARISResponse, Action, Observation


def test_aris_core_surface_is_available() -> None:
    assert aris_core.Settings is Settings
    assert settings.FRONTEND_INDEX_FILE
    assert Path(settings.FRONTEND_INDEX_FILE).as_posix().endswith("apps/web/dist/index.html")
    assert Path(settings.ARIS_MEMORY_DIR).as_posix().endswith("runtime/memories")
    assert Path(settings.ARIS_PROJECTS_ROOT).as_posix().endswith("runtime/projects")
    assert Path(settings.ARIS_PRESETS_FILE).as_posix().endswith("config/apps/aiida/presets.yaml")
    assert Path(settings.ARIS_AIIDA_SETTINGS_FILE).as_posix().endswith("config/apps/aiida/settings.yaml")
    assert Path(settings.ARIS_SCRIPT_ARCHIVE_DIR).as_posix().endswith("runtime/scripts")
    assert BaseARISDeps.__name__ == "BaseARISDeps"
    assert JSONMemory.__name__ == "JSONMemory"
    assert ARISMemoryState.__name__ == "ARISMemoryState"
    assert Executor.__name__ == "Executor"
    assert Perceptor.__name__ == "Perceptor"
    assert Observation(raw="ok").source == "default"
    assert Action(name="noop").payload == {}
    assert ARISResponse.__name__ == "ARISResponse"
    assert ARISResponse(answer="ok", thought_process=[]).is_successful is True


def test_aris_aiida_surface_is_available() -> None:
    assert aiida_researcher is not None
    assert callable(get_aiida_worker_client)
    assert callable(get_chat_snapshot)
    assert aiida_router is not None


def test_api_entrypoints_import_with_aris_paths() -> None:
    from apps.api.main import app as api_app
    from src.app_api import app as legacy_api_app

    assert api_app is legacy_api_app
    assert api_app.title == "ARIS Central Hub"


def test_json_memory_defaults_to_runtime_settings(tmp_path) -> None:
    original_dir = settings.ARIS_MEMORY_DIR
    settings.ARIS_MEMORY_DIR = str(tmp_path)
    try:
        memory = JSONMemory(namespace="aris-default-path")
        assert Path(memory.file_path).parent == tmp_path
    finally:
        settings.ARIS_MEMORY_DIR = original_dir


def test_json_memory_uses_canonical_namespace_state(tmp_path) -> None:
    memory = JSONMemory(namespace="aris_v2_global", storage_path=str(tmp_path))
    memory.set_kv("migrated", True)

    reloaded = JSONMemory(namespace="aris_v2_global", storage_path=str(tmp_path))

    assert reloaded.file_path.endswith("history_aris_v2_global.json")
    assert reloaded.get_kv("migrated") is True


def test_runtime_env_values_are_normalized_to_runtime_root(monkeypatch) -> None:
    monkeypatch.setenv("ARIS_MEMORY_DIR", "engines/aiida/data/memories")
    monkeypatch.setenv("ARIS_PROJECTS_ROOT", "data/projects")
    monkeypatch.setenv("ARIS_SCRIPT_ARCHIVE_DIR", "engines/aiida/data/scripts")

    config = Settings(_env_file=None)

    assert Path(config.ARIS_MEMORY_DIR).as_posix().endswith("runtime/memories")
    assert Path(config.ARIS_PROJECTS_ROOT).as_posix().endswith("runtime/projects")
    assert Path(config.ARIS_SCRIPT_ARCHIVE_DIR).as_posix().endswith("runtime/scripts")
