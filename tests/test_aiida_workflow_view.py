from __future__ import annotations

from src.sab_engines.aiida.presenters import workflow_view


def test_enrich_submission_draft_keeps_cutoffs_under_parameters() -> None:
    payload = {
        "process_label": "quantumespresso.pw.relax",
        "inputs": {
            "base": {
                "pw": {
                    "parameters": {
                        "SYSTEM": {
                            "ecutwfc": 60,
                            "ecutrho": 480,
                        }
                    }
                }
            }
        },
        "recommended_inputs": {
            "ecutwfc": 60,
            "ecutrho": 480,
        },
        "meta": {},
    }

    normalized = workflow_view.enrich_submission_draft_payload(payload)
    all_inputs = normalized["all_inputs"]

    assert "ecutwfc" not in all_inputs
    assert "ecutrho" not in all_inputs
    assert "base.pw.parameters.SYSTEM.ecutwfc" in all_inputs
    assert "base.pw.parameters.SYSTEM.ecutrho" in all_inputs


def test_enrich_submission_draft_adds_available_codes_metadata(monkeypatch) -> None:
    fake_port_spec = {
        "entry_point": "quantumespresso.pw.relax",
        "namespaces": ["base", "base.pw", "base.pw.parameters", "base_final", "base_final.pw"],
        "ports": [
            {"path": "code", "kind": "code", "required": False},
            {"path": "base.pw.code", "kind": "code", "required": True},
            {"path": "base_final.pw.code", "kind": "code", "required": False},
        ],
        "code_paths": ["code", "base.pw.code", "base_final.pw.code"],
    }
    fake_codes = [
        {
            "value": "pw@localhost",
            "label": "pw@localhost",
            "code_label": "pw",
            "computer_label": "localhost",
            "plugin": "quantumespresso.pw",
            "pk": 11,
        }
    ]

    monkeypatch.setattr(workflow_view, "_load_workflow_port_spec", lambda _entry_points: fake_port_spec)
    monkeypatch.setattr(workflow_view, "_query_available_codes", lambda _required_plugin: fake_codes)

    payload = {
        "process_label": "quantumespresso.pw.relax",
        "inputs": {
            "base": {
                "pw": {
                    "parameters": {"SYSTEM": {"ecutwfc": 60}},
                }
            }
        },
        "meta": {},
    }

    normalized = workflow_view.enrich_submission_draft_payload(payload)
    meta = normalized["meta"]

    assert meta["required_code_plugin"] == "quantumespresso.pw"
    assert meta["available_codes"] == fake_codes
    port_spec = meta["port_spec"]
    assert set(fake_port_spec["namespaces"]).issubset(set(port_spec["namespaces"]))
    assert set(fake_port_spec["code_paths"]).issubset(set(port_spec["code_paths"]))
    assert meta["workchain_entry_point"] == "quantumespresso.pw.relax"


def test_enrich_submission_draft_builds_fallback_port_spec_and_codes(monkeypatch) -> None:
    monkeypatch.setattr(workflow_view, "_load_workflow_port_spec", lambda _entry_points: None)
    monkeypatch.setattr(workflow_view, "_query_available_codes", lambda _required_plugin: [])

    payload = {
        "process_label": "PwRelaxWorkChain",
        "inputs": {
            "code": "pw-7.5@localhost",
            "base": {
                "pw": {
                    "code": "pw-7.5@localhost",
                    "parameters": {"SYSTEM": {"ecutwfc": 60}},
                }
            },
        },
        "meta": {},
    }

    normalized = workflow_view.enrich_submission_draft_payload(payload)
    meta = normalized["meta"]
    port_spec = meta["port_spec"]
    namespaces = set(port_spec["namespaces"])

    assert "base" in namespaces
    assert "base_final" in namespaces
    assert "metadata" in namespaces
    assert "metadata.options" in namespaces
    assert "metadata.options.resources" in namespaces
    assert "code" not in set(port_spec["code_paths"])
    assert "base_final.pw.code" in set(port_spec["code_paths"])
    assert any(entry["value"] == "pw-7.5@localhost" for entry in meta["available_codes"])


def test_query_available_codes_uses_bridge_resources_fallback(monkeypatch) -> None:
    from src.sab_engines.aiida import client as aiida_client

    def fake_request_json_sync(method: str, path: str, **kwargs):
        _ = kwargs
        assert method == "GET"
        assert path == "/resources"
        return {
            "codes": [
                {
                    "label": "qe-750-pw",
                    "computer_label": "lucia",
                    "default_plugin": "quantumespresso.pw",
                },
                {
                    "label": "qe-750-ph",
                    "computer_label": "lucia",
                    "default_plugin": "quantumespresso.ph",
                },
                {
                    "value": "qe-legacy@lucia",
                },
            ]
        }

    monkeypatch.setattr(aiida_client.bridge_service, "request_json_sync", fake_request_json_sync)

    codes = workflow_view._query_available_codes("quantumespresso.pw")
    codes_by_value = {str(item.get("value")): item for item in codes}

    assert "qe-750-pw@lucia" in codes_by_value
    assert codes_by_value["qe-750-pw@lucia"]["is_compatible"] is True
    assert "qe-750-ph@lucia" in codes_by_value
    assert "qe-legacy@lucia" in codes_by_value
