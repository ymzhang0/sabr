from __future__ import annotations

import pytest

from src.aris_apps.aiida import specializations


@pytest.mark.anyio
async def test_quantumespresso_specialization_activates_from_structure_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        specializations,
        "get_context_nodes",
        lambda node_ids: [{"pk": pk, "node_type": "StructureData"} for pk in node_ids],
    )

    async def _fake_get_plugins(*, force_refresh: bool = False) -> list[str]:
        assert force_refresh is False
        return ["quantumespresso.pw.base", "core.arithmetic.add_multiply"]

    monkeypatch.setattr(specializations.aiida_worker_client, "get_plugins", _fake_get_plugins)

    payload = await specializations.build_active_specializations_payload(context_node_ids=[42])

    assert payload["environment"] == {
        "selected": None,
        "resolved": "quantumespresso",
        "auto_switch": True,
    }
    assert payload["context"]["context_node_types"] == ["StructureData"]
    assert payload["context"]["worker_plugins_available"] is True

    active_names = {item["name"] for item in payload["active_specializations"]}
    assert active_names == {"general", "quantumespresso"}

    qe_actions = [item for item in payload["chips"] if item["specialization"] == "quantumespresso"]
    assert {item["command"] for item in qe_actions} == {"/bands", "/dos", "/vc-relax"}
    assert all(item["enabled"] is True for item in qe_actions)
    assert {section["label"] for section in payload["slash_menu"]} == {"General", "Quantum ESPRESSO"}


@pytest.mark.anyio
async def test_quantumespresso_actions_disable_without_structure_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(specializations, "get_context_nodes", lambda _node_ids: [])

    async def _fake_get_plugins(*, force_refresh: bool = False) -> list[str]:
        assert force_refresh is False
        return ["core.arithmetic.add_multiply"]

    monkeypatch.setattr(specializations.aiida_worker_client, "get_plugins", _fake_get_plugins)

    payload = await specializations.build_active_specializations_payload(
        context_node_ids=[],
        resource_plugins=["quantumespresso.pw"],
    )

    qe_summary = next(item for item in payload["active_specializations"] if item["name"] == "quantumespresso")
    assert qe_summary["active"] is True
    assert qe_summary["reasons"] == ["resource_plugins"]

    qe_actions = [item for item in payload["chips"] if item["specialization"] == "quantumespresso"]
    assert qe_actions
    assert all(item["enabled"] is False for item in qe_actions)
    assert all("Requires context node types" in str(item["disabled_reason"]) for item in qe_actions)


@pytest.mark.anyio
async def test_manual_environment_selection_forces_specialization_when_auto_switch_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(specializations, "get_context_nodes", lambda _node_ids: [])

    async def _fake_get_plugins(*, force_refresh: bool = False) -> list[str]:
        assert force_refresh is False
        return ["core.arithmetic.add_multiply"]

    monkeypatch.setattr(specializations.aiida_worker_client, "get_plugins", _fake_get_plugins)

    payload = await specializations.build_active_specializations_payload(
        context_node_ids=[],
        selected_environment="quantumespresso",
        auto_switch=False,
    )

    assert payload["environment"] == {
        "selected": "quantumespresso",
        "resolved": "quantumespresso",
        "auto_switch": False,
    }
    qe_summary = next(item for item in payload["active_specializations"] if item["name"] == "quantumespresso")
    assert qe_summary["reasons"] == ["manual_selection"]
