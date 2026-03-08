from __future__ import annotations

import importlib


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
