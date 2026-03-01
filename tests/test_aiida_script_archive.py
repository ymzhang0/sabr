from __future__ import annotations

import pytest

from src.sab_engines.aiida.agent import tools


@pytest.mark.anyio
async def test_run_python_code_success_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "POST"
        assert path == "/management/run-python"
        assert kwargs.get("json", {}).get("script") == "print('hello')"
        return {"success": True, "output": "hello"}

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    result = await tools.run_python_code("print('hello')")

    assert result == "hello"


@pytest.mark.anyio
async def test_run_python_code_returns_missing_module_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "POST"
        assert path == "/management/run-python"
        return {
            "success": False,
            "error": (
                "Traceback (most recent call last):\n"
                "  File \"<string>\", line 1, in <module>\n"
                "ModuleNotFoundError: No module named 'aiida_pseudo.data.family'\n"
            ),
            "output": "",
        }

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    result = await tools.run_python_code("import aiida_pseudo")

    assert isinstance(result, dict)
    assert result["missing_module"] == "aiida_pseudo.data.family"
    assert "missing this Python module" in result["hint"]


@pytest.mark.anyio
async def test_register_specialized_skill_calls_registry_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "POST"
        assert path == "/registry/register"
        body = kwargs.get("json", {})
        assert body["skill_name"] == "relax_helper"
        assert "def main" in body["script"]
        return {"status": "registered", "skill_name": body["skill_name"]}

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    payload = await tools.register_specialized_skill(
        skill_name="relax_helper",
        script="def main(params):\n    return params\n",
        description="Reusable relax helper",
        overwrite=True,
    )

    assert isinstance(payload, dict)
    assert payload["status"] == "registered"
    assert payload["skill_name"] == "relax_helper"


@pytest.mark.anyio
async def test_execute_specialized_skill_calls_execute_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "POST"
        assert path == "/execute/relax_helper"
        assert kwargs.get("json") == {"params": {"pk": 264}}
        return {"success": True, "result": {"submitted": [1001]}}

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    payload = await tools.execute_specialized_skill("relax_helper", {"pk": 264})

    assert isinstance(payload, dict)
    assert payload["success"] is True
    assert payload["result"]["submitted"] == [1001]


@pytest.mark.anyio
async def test_list_registered_skills_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request_json(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "GET"
        assert path == "/registry/list"
        return {
            "count": 2,
            "items": [
                {"name": "skill_a", "description": "A", "updated_at": "2026-03-01T00:00:00Z"},
                {"name": "skill_b", "entrypoint": "main(params)"},
            ],
        }

    monkeypatch.setattr(tools, "request_json", _fake_request_json)

    payload = await tools.list_registered_skills()

    assert isinstance(payload, dict)
    assert payload["count"] == 2
    assert payload["items"][0]["name"] == "skill_a"
    assert payload["items"][1]["name"] == "skill_b"


def test_list_registered_skills_sync_handles_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_request_json_sync(method: str, path: str, **kwargs):  # noqa: ANN003
        assert method == "GET"
        assert path == "/registry/list"
        raise RuntimeError("worker unavailable")

    monkeypatch.setattr(tools, "request_json_sync", _fake_request_json_sync)

    payload = tools.list_registered_skills_sync()

    assert payload == {"count": 0, "items": []}


def test_summarize_worker_error_prefers_traceback_root_cause() -> None:
    error_text = (
        "Traceback (most recent call last):\n"
        "  File \"<string>\", line 2, in <module>\n"
        "ImportError: cannot import name 'load_dbenv' from 'aiida'\n"
    )

    summary = tools._summarize_worker_error(error_text)

    assert summary == "ImportError: cannot import name 'load_dbenv' from 'aiida'"
