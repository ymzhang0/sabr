from __future__ import annotations

import importlib
import logging


def test_legacy_logging_module_resolves_to_aris_logging_core() -> None:
    legacy_module = importlib.import_module("src.sab_core.logging_utils")
    canonical_module = importlib.import_module("src.aris_core.logging.core")
    legacy_top_level_module = importlib.import_module("sab_core.logging_utils")
    canonical_top_level_module = importlib.import_module("aris_core.logging.core")

    assert legacy_module is canonical_module
    assert legacy_top_level_module is canonical_top_level_module
    assert legacy_top_level_module is canonical_module


def test_aris_logging_package_exports_canonical_functions() -> None:
    from src.aris_core.logging import get_log_buffer_snapshot, log_event, setup_logging

    assert callable(setup_logging)
    assert callable(get_log_buffer_snapshot)
    assert log_event("test.event", value=1).startswith("evt=test.event")


def test_logging_env_resolution_prefers_aris_names(monkeypatch) -> None:
    canonical_module = importlib.import_module("src.aris_core.logging.core")
    monkeypatch.setenv("ARIS_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("SABR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ARIS_ACCESS_LOG_LEVEL", "CRITICAL")
    monkeypatch.setenv("SABR_ACCESS_LOG_LEVEL", "INFO")

    resolved_level = canonical_module.setup_logging(default_level="INFO")

    assert resolved_level == "ERROR"
    assert logging.getLogger("uvicorn.access").level == logging.CRITICAL


def test_logging_buffer_size_resolution_prefers_aris_name(monkeypatch) -> None:
    canonical_module = importlib.import_module("src.aris_core.logging.core")
    monkeypatch.setenv("ARIS_LOG_BUFFER_SIZE", "777")
    monkeypatch.setenv("SABR_LOG_BUFFER_SIZE", "333")

    assert canonical_module._get_compat_env_int(  # noqa: SLF001
        "ARIS_LOG_BUFFER_SIZE",
        "SABR_LOG_BUFFER_SIZE",
        default=600,
    ) == 777
