from __future__ import annotations

import importlib


def test_legacy_aiida_modules_resolve_to_aris_modules() -> None:
    module_pairs = (
        ("src.sab_engines.aiida.client", "src.aris_apps.aiida.client"),
        ("src.sab_engines.aiida.router", "src.aris_apps.aiida.router"),
        ("src.sab_engines.aiida.chat.service", "src.aris_apps.aiida.chat.service"),
        ("src.sab_engines.aiida.presenters.workflow_view", "src.aris_apps.aiida.presenters.workflow_view"),
        ("src.sab_engines.aiida.agent.tools", "src.aris_apps.aiida.agent.tools"),
    )

    for legacy_name, canonical_name in module_pairs:
        legacy_module = importlib.import_module(legacy_name)
        canonical_module = importlib.import_module(canonical_name)
        assert legacy_module is canonical_module
