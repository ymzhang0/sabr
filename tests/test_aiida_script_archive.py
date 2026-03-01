from __future__ import annotations

import json
import re

import pytest

from src.sab_engines.aiida.agent import tools


@pytest.mark.anyio
async def test_run_python_code_archives_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(tools, "_SCRIPT_ARCHIVE_DIR", tmp_path)

    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "POST"
        assert path == "/management/run-python"
        assert kwargs.get("json", {}).get("script") == "print('archive')"
        pending_metadata_files = list(tmp_path.glob("script_*.json"))
        assert len(pending_metadata_files) == 1
        pending_metadata = json.loads(pending_metadata_files[0].read_text(encoding="utf-8"))
        assert pending_metadata["status"] == "pending"
        return {"success": True, "output": "Submitted as PK 102 and Node #103"}

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    result = await tools.run_python_code(
        "print('archive')",
        intent="relax structures with pseudodojo",
        nodes_involved=[264, "264"],
        turn_id=1,
    )

    assert isinstance(result, str)
    assert "PK 102" in result

    metadata_files = list(tmp_path.glob("script_*.json"))
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))

    assert re.match(r"script_\d{8}_turn1_v1", str(metadata.get("script_id")))
    assert metadata["status"] == "success"
    assert metadata["intent"] == "relax structures with pseudodojo"
    assert metadata["nodes_involved"] == [264]
    assert set(metadata["created_pks"]) == {102, 103}

    script_path = tmp_path / f"{metadata['script_id']}.py"
    assert script_path.exists()
    assert script_path.read_text(encoding="utf-8") == "print('archive')"


@pytest.mark.anyio
async def test_run_python_code_archives_error(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(tools, "_SCRIPT_ARCHIVE_DIR", tmp_path)

    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "POST"
        assert path == "/management/run-python"
        return {
            "success": False,
            "error": (
                "Traceback (most recent call last):\n"
                "  File \"<string>\", line 1, in <module>\n"
                "ModuleNotFoundError: No module named 'aiida_quantumespresso'\n"
            ),
            "output": "",
        }

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    result = await tools.run_python_code(
        "raise RuntimeError('boom')",
        intent="test failing script",
        nodes_involved=[11],
        turn_id=2,
    )

    assert isinstance(result, dict)
    assert "ModuleNotFoundError" in result["error"]
    assert result["missing_module"] == "aiida_quantumespresso"
    assert "missing this Python module" in result["hint"]

    metadata_files = list(tmp_path.glob("script_*.json"))
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["status"] == "error"
    assert "ModuleNotFoundError" in metadata["error_message"]
    assert metadata["missing_module"] == "aiida_quantumespresso"
    assert metadata["nodes_involved"] == [11]


@pytest.mark.anyio
async def test_search_script_archive_filters_by_keyword_and_nodes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "_SCRIPT_ARCHIVE_DIR", tmp_path)

    meta_a = {
        "script_id": "script_20260301_turn1_v1",
        "timestamp": "2026-03-01T00:00:00+00:00",
        "intent": "relax structures with pseudodojo",
        "nodes_involved": [264, 300],
        "status": "success",
        "created_pks": [5001],
        "error_message": None,
    }
    meta_b = {
        "script_id": "script_20260301_turn2_v1",
        "timestamp": "2026-03-01T00:01:00+00:00",
        "intent": "inspect failed bands workflow",
        "nodes_involved": [999],
        "status": "error",
        "created_pks": [],
        "error_message": "missing pseudos",
    }
    (tmp_path / "script_20260301_turn1_v1.py").write_text("print('relax')", encoding="utf-8")
    (tmp_path / "script_20260301_turn2_v1.py").write_text("print('inspect')", encoding="utf-8")
    (tmp_path / "script_20260301_turn1_v1.json").write_text(
        json.dumps(meta_a, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    (tmp_path / "script_20260301_turn2_v1.json").write_text(
        json.dumps(meta_b, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    payload = await tools.search_script_archive(
        keyword="relax",
        nodes_involved=[264],
        include_source=True,
        limit=10,
    )

    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["script_id"] == "script_20260301_turn1_v1"
    assert item["nodes_involved"] == [264, 300]
    assert "print('relax')" in item["script"]
