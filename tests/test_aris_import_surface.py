from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("GOOGLE_API_KEY", "dummy")

import sab_core

from src.aris_apps.aiida.agent.researcher import aiida_researcher
from src.aris_apps.aiida.api.router import router as aiida_router
from src.aris_apps.aiida.chat import get_chat_snapshot
from src.aris_apps.aiida.client import get_aiida_worker_client
from src.aris_core.config import Settings, settings
from src.aris_core.deps import BaseSABRDeps
from src.aris_core.memory import JSONMemory
from src.aris_core.protocols import Executor, Perceptor
from src.aris_core.schema import Action, Observation, SABRResponse


def test_aris_core_surface_is_available() -> None:
    assert sab_core.Settings is Settings
    assert settings.FRONTEND_INDEX_FILE
    assert Path(settings.FRONTEND_INDEX_FILE).as_posix().endswith("apps/web/dist/index.html")
    assert Path(settings.SABR_MEMORY_DIR).as_posix().endswith("runtime/memories")
    assert Path(settings.SABR_PROJECTS_ROOT).as_posix().endswith("runtime/projects")
    assert Path(settings.ARIS_SCRIPT_ARCHIVE_DIR).as_posix().endswith("runtime/scripts")
    assert BaseSABRDeps.__name__ == "BaseSABRDeps"
    assert JSONMemory.__name__ == "JSONMemory"
    assert Executor.__name__ == "Executor"
    assert Perceptor.__name__ == "Perceptor"
    assert Observation(raw="ok").source == "default"
    assert Action(name="noop").payload == {}
    assert SABRResponse(answer="ok", thought_process=[]).is_successful is True


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
    original_dir = settings.SABR_MEMORY_DIR
    settings.SABR_MEMORY_DIR = str(tmp_path)
    try:
        memory = JSONMemory(namespace="aris-default-path")
        assert Path(memory.file_path).parent == tmp_path
    finally:
        settings.SABR_MEMORY_DIR = original_dir


def test_legacy_runtime_env_values_are_normalized_to_runtime_root(monkeypatch) -> None:
    monkeypatch.setenv("SABR_MEMORY_DIR", "engines/aiida/data/memories")
    monkeypatch.setenv("SABR_PROJECTS_ROOT", "data/projects")
    monkeypatch.setenv("SABR_SCRIPT_ARCHIVE_DIR", "src/sab_engines/aiida/data/scripts")

    config = Settings(_env_file=None)

    assert Path(config.SABR_MEMORY_DIR).as_posix().endswith("runtime/memories")
    assert Path(config.SABR_PROJECTS_ROOT).as_posix().endswith("runtime/projects")
    assert Path(config.ARIS_SCRIPT_ARCHIVE_DIR).as_posix().endswith("runtime/scripts")
