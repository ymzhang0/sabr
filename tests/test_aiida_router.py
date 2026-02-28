"""Tests for AiiDA frontend process serialization and process-detail enrichment."""

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
        11: (root_inputs, []),
    }

    aiida_router._attach_tree_links(tree, links_by_pk)

    assert tree["inputs"] == root_inputs
    assert tree["outputs"] == []
    assert tree["children"]["child"]["inputs"] == []
    assert tree["children"]["child"]["outputs"] == []


@pytest.mark.anyio
async def test_enrich_process_detail_payload_always_exposes_link_arrays() -> None:
    payload = {"summary": {"pk": None}}

    enriched = await aiida_router._enrich_process_detail_payload(payload)

    assert enriched["inputs"] == []
    assert enriched["outputs"] == []
