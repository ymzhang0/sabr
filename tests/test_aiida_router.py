"""Tests for AiiDA frontend process serialization and process-detail enrichment."""

from types import SimpleNamespace

import pytest

from src.sab_engines.aiida import router as aiida_router
from src.sab_engines.aiida.router import (
    _coerce_chat_metadata,
    _extract_folder_preview,
    _serialize_processes,
)


def test_serialize_processes_passes_preview_without_modification() -> None:
    preview = {
        "formula": "Si2",
        "atom_count": 2,
    }
    processes = [
        {
            "pk": 101,
            "label": "Silicon bulk",
            "state": "finished",
            "node_type": "StructureData",
            "formula": "Si2",
            "preview": preview,
        }
    ]

    serialized = _serialize_processes(processes)

    assert serialized[0]["preview"] is preview
    assert serialized[0]["preview"] == preview


def test_serialize_processes_does_not_add_preview_when_missing() -> None:
    processes = [
        {
            "pk": 202,
            "label": "Relaxation",
            "state": "running",
            "node_type": "ProcessNode",
        }
    ]

    serialized = _serialize_processes(processes)

    assert "preview" not in serialized[0]


def test_serialize_processes_passes_preview_info_without_modification() -> None:
    preview_info = {
        "array_names": ["kpoints", "energies"],
    }
    processes = [
        {
            "pk": 303,
            "label": "Bands postprocess",
            "state": "finished",
            "node_type": "XyData",
            "preview_info": preview_info,
        }
    ]

    serialized = _serialize_processes(processes)

    assert serialized[0]["preview_info"] is preview_info
    assert serialized[0]["preview_info"] == preview_info


def test_serialize_processes_passes_process_label() -> None:
    processes = [
        {
            "pk": 404,
            "label": "EPW run",
            "state": "running",
            "node_type": "ProcessNode",
            "process_label": "EpwCalculation",
        }
    ]

    serialized = _serialize_processes(processes)

    assert serialized[0]["process_label"] == "EpwCalculation"


def test_coerce_chat_metadata_drops_empty_keys() -> None:
    metadata = {
        " current_focus_pk ": 123,
        "": "skip",
        "   ": "skip",
    }

    coerced = _coerce_chat_metadata(metadata)

    assert coerced == {"current_focus_pk": 123}


def test_extract_folder_preview_ignores_generic_node_metadata() -> None:
    payload = {
        "pk": 55,
        "node_type": "FolderData",
        "label": "retrieved",
        "state": "stored",
    }

    preview = _extract_folder_preview(payload)

    assert preview is None


def test_extract_folder_preview_prefers_repository_file_listing() -> None:
    payload = {
        "pk": 55,
        "node_type": "FolderData",
        "repository": {
            "files": [
                {"name": "aiida.out"},
                {"name": "scheduler.stderr"},
                {"name": "_scheduler-stdout.txt"},
            ]
        },
    }

    preview = _extract_folder_preview(payload)

    assert preview == {"filenames": ["aiida.out", "scheduler.stderr", "_scheduler-stdout.txt"]}


def test_attach_tree_links_sets_inputs_and_outputs_on_each_tree_node() -> None:
    tree = {
        "pk": 11,
        "children": {
            "child": {
                "pk": 22,
                "children": {},
            }
        },
    }
    root_inputs = [{"link_label": "structure", "node_type": "StructureData", "pk": 5}]
    links_by_pk = {
        11: (root_inputs, [], [], []),
    }

    aiida_router._attach_tree_links(tree, links_by_pk)

    assert tree["inputs"] == {
        "structure": {"link_label": "structure", "node_type": "StructureData", "pk": 5}
    }
    assert tree["outputs"] == {}
    assert tree["children"]["child"]["inputs"] == {}
    assert tree["children"]["child"]["outputs"] == {}


@pytest.mark.anyio
async def test_enrich_process_detail_payload_always_exposes_link_arrays() -> None:
    payload = {"summary": {"pk": None}}

    enriched = await aiida_router._enrich_process_detail_payload(payload)

    assert enriched["inputs"] == {}
    assert enriched["outputs"] == {}


def test_clear_pending_submission_memory_sets_none() -> None:
    captured: dict[str, object] = {}

    class _DummyMemory:
        def set_kv(self, key: str, value: object) -> None:
            captured[key] = value

    state = type("State", (), {"memory": _DummyMemory()})()

    aiida_router._clear_pending_submission_memory(state)

    assert captured[aiida_router.PENDING_SUBMISSION_KEY] is None


@pytest.mark.anyio
async def test_frontend_active_specializations_normalizes_query_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def _fake_build_active_specializations_payload(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "chips": [],
            "slash_menu": [],
            "active_specializations": [],
            "inactive_specializations": [],
            "environment": {"selected": None, "resolved": "general", "auto_switch": True},
            "context": {
                "context_node_ids": [11, 22],
                "context_node_types": [],
                "project_tags": ["qe", "quantumespresso"],
                "resource_plugins": ["quantumespresso.pw"],
                "worker_plugins": [],
                "worker_plugins_available": True,
            },
        }

    monkeypatch.setattr(aiida_router, "build_active_specializations_payload", _fake_build_active_specializations_payload)

    response = await aiida_router.frontend_active_specializations(
        context_node_ids=[11, 22],
        project_tags=[" qe, quantumespresso ", "QE"],
        resource_plugins=[" quantumespresso.pw , quantumespresso.pw "],
        selected_environment=None,
        auto_switch=True,
    )

    assert captured == {
        "context_node_ids": [11, 22],
        "project_tags": ["qe", "quantumespresso"],
        "resource_plugins": ["quantumespresso.pw"],
        "selected_environment": None,
        "auto_switch": True,
    }
    assert response["environment"]["resolved"] == "general"


@pytest.mark.anyio
async def test_submit_bridge_workchain_single_adds_submitted_pk(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request_json(method: str, path: str, json: dict[str, object]):  # noqa: ARG001
        assert method == "POST"
        assert path == "/submission/submit"
        assert "draft" in json
        return {"status": "SUBMITTED", "pk": 321}

    monkeypatch.setattr(aiida_router, "request_json", _fake_request_json)

    captured: dict[str, object] = {}

    class _DummyMemory:
        def set_kv(self, key: str, value: object) -> None:
            captured[key] = value

    state = SimpleNamespace(memory=_DummyMemory())
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    payload = aiida_router.SubmissionDraftRequest(draft={"builder": {"structure_pk": 11}})

    response = await aiida_router.submit_bridge_workchain(request, payload)

    assert response["submitted_pks"] == [321]
    assert response["process_pks"] == [321]
    assert captured[aiida_router.PENDING_SUBMISSION_KEY] is None


@pytest.mark.anyio
async def test_submit_bridge_workchain_batch_collects_submitted_pks(monkeypatch: pytest.MonkeyPatch) -> None:
    submitted = [901, 902, 903]
    call_count = 0

    async def _fake_request_json(method: str, path: str, json: dict[str, object]):  # noqa: ARG001
        nonlocal call_count
        assert method == "POST"
        assert path == "/submission/submit"
        assert "draft" in json
        pk = submitted[call_count]
        call_count += 1
        return {"status": "SUBMITTED", "pk": pk}

    monkeypatch.setattr(aiida_router, "request_json", _fake_request_json)

    captured: dict[str, object] = {}

    class _DummyMemory:
        def set_kv(self, key: str, value: object) -> None:
            captured[key] = value

    state = SimpleNamespace(memory=_DummyMemory())
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    payload = aiida_router.SubmissionDraftRequest(
        draft=[
            {"builder": {"structure_pk": 11}},
            {"builder": {"structure_pk": 22}},
            {"builder": {"structure_pk": 33}},
        ]
    )

    response = await aiida_router.submit_bridge_workchain(request, payload)

    assert response["status"] == "SUBMITTED_BATCH"
    assert response["submitted_pks"] == submitted
    assert response["process_pks"] == submitted
    assert response["failures"] == []
    assert len(response["responses"]) == 3
    assert captured[aiida_router.PENDING_SUBMISSION_KEY] is None


@pytest.mark.anyio
async def test_frontend_node_hover_metadata_resolves_formula_spacegroup_and_node_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        aiida_router,
        "get_context_nodes",
        lambda _ids: [
            {
                "pk": 11,
                "node_type": "StructureData",
                "formula": "Si2",
                "attributes": {
                    "spacegroup": {
                        "symbol": "Fm-3m",
                        "number": 225,
                    }
                },
            }
        ],
    )
    monkeypatch.setattr(aiida_router.hub, "start", lambda: None)
    monkeypatch.setattr(aiida_router.hub, "_current_profile", "test-profile")

    response = await aiida_router.frontend_node_hover_metadata(11)

    assert response.pk == 11
    assert response.formula == "Si2"
    assert response.spacegroup == "Fm-3m (225)"
    assert response.node_type == "StructureData"


@pytest.mark.anyio
async def test_frontend_node_hover_metadata_returns_safe_fallback_when_node_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(aiida_router, "get_context_nodes", lambda _ids: [])
    monkeypatch.setattr(aiida_router.hub, "start", lambda: None)
    monkeypatch.setattr(aiida_router.hub, "_current_profile", "test-profile")

    response = await aiida_router.frontend_node_hover_metadata(9999)

    assert response.pk == 9999
    assert response.formula is None
    assert response.spacegroup is None
    assert response.node_type == "Unknown"


@pytest.mark.anyio
async def test_frontend_node_script_proxies_worker_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "pk": 88,
        "node_type": "StructureData",
        "language": "python",
        "script": "from ase import Atoms\natoms = Atoms(...)",
    }

    async def _fake_request_json(method: str, path: str, **_: object) -> dict[str, object]:
        assert method == "GET"
        assert path == "/management/nodes/88/script"
        return expected

    monkeypatch.setattr(aiida_router, "request_json", _fake_request_json)

    response = await aiida_router.frontend_node_script(88)

    assert response.model_dump() == expected


@pytest.mark.anyio
async def test_frontend_node_script_falls_back_to_node_summary_when_worker_route_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _fake_request_json(method: str, path: str, **_: object) -> dict[str, object]:
        assert method == "GET"
        calls.append(path)
        if path == "/management/nodes/77/script":
            raise aiida_router.BridgeAPIError(status_code=404, message="Not found", payload={"error": "Not found"})
        if path == "/management/nodes/77":
            return {
                "pk": 77,
                "node_type": "Dict",
                "attributes": {"ecutwfc": 50, "conv_thr": 1.0e-8},
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(aiida_router, "request_json", _fake_request_json)

    response = await aiida_router.frontend_node_script(77)

    assert calls == ["/management/nodes/77/script", "/management/nodes/77"]
    assert response.pk == 77
    assert response.node_type == "Dict"
    assert "ecutwfc" in response.script


@pytest.mark.anyio
async def test_frontend_clone_process_draft_enriches_worker_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    worker_payload = {
        "process_label": "PwBaseWorkChain",
        "entry_point": "aiida.workflows:quantumespresso.pw.base",
        "inputs": {"structure": 11, "pw": {"code": "pw@localhost"}},
        "meta": {
            "draft": {
                "entry_point": "aiida.workflows:quantumespresso.pw.base",
                "inputs": {"structure": 11, "pw": {"code": "pw@localhost"}},
            }
        },
    }
    enriched_payload = {
        "process_label": "PwBaseWorkChain",
        "inputs": {"structure": 11, "pw": {"code": "pw@localhost"}},
        "meta": {"draft": worker_payload["meta"]["draft"], "port_spec": {"entry_point": "aiida.workflows:quantumespresso.pw.base"}},
    }

    async def _fake_request_json(method: str, path: str, **_: object) -> dict[str, object]:
        assert method == "GET"
        assert path == "/process/321/clone-draft"
        return worker_payload

    monkeypatch.setattr(aiida_router, "request_json", _fake_request_json)
    monkeypatch.setattr(aiida_router, "enrich_submission_draft_payload", lambda payload: enriched_payload if payload == worker_payload else payload)

    response = await aiida_router.frontend_clone_process_draft("321")

    assert response == enriched_payload
