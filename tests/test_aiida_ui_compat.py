from __future__ import annotations

import importlib

from src.aris_legacy.nicegui import THEMES as legacy_themes
from src.aris_legacy.nicegui import create_aiida_layout as legacy_layout
from src.aris_apps.aiida.paths import logs_template, static_dir


def test_aris_aiida_ui_modules_resolve_to_legacy_implementation() -> None:
    module_pairs = (
        ("src.aris_apps.aiida.ui.controller", "src.aris_legacy.nicegui.controller"),
        ("src.aris_apps.aiida.ui.layout", "src.aris_legacy.nicegui.layout"),
        ("src.aris_apps.aiida.ui.themes", "src.aris_legacy.nicegui.themes"),
        ("src.sab_engines.aiida.ui.legacy_nicegui.layout", "src.aris_legacy.nicegui.layout"),
    )

    for shim_name, legacy_name in module_pairs:
        shim_module = importlib.import_module(shim_name)
        legacy_module = importlib.import_module(legacy_name)
        assert shim_module is legacy_module


def test_aris_aiida_ui_exports_match_legacy_exports() -> None:
    from src.aris_apps.aiida.ui.legacy_nicegui import THEMES as app_themes
    from src.aris_apps.aiida.ui.legacy_nicegui import create_aiida_layout as app_layout

    assert app_themes is legacy_themes
    assert app_layout is legacy_layout


def test_aris_aiida_static_paths_prefer_canonical_location() -> None:
    assert static_dir().as_posix().endswith("src/aris_apps/aiida/static")
    assert logs_template().as_posix().endswith("src/aris_apps/aiida/static/logs_template.html")
