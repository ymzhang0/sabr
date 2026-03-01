"""Tests for pre-submission validation flow in the AiiDA researcher agent."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from src.sab_engines.aiida.deps import AiiDADeps

os.environ.setdefault("GOOGLE_API_KEY", "dummy")

from src.sab_engines.aiida.agent import researcher  # noqa: E402


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(deps=AiiDADeps())


@pytest.mark.anyio
async def test_submit_new_workflow_validates_before_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def _fake_draft(workchain: str, structure_pk: int, code: str, protocol: str):
        calls.append("draft")
        assert workchain == "quantumespresso.pw.base"
        assert structure_pk == 11
        assert code == "pw@localhost"
        assert protocol == "moderate"
        return {"status": "DRAFT_READY", "builder": {"workchain": workchain}}

    async def _fake_validate(draft_data: dict):
        calls.append("validate")
        assert draft_data.get("status") == "DRAFT_READY"
        return {"status": "VALIDATION_OK", "warnings": ["resource estimate is high"], "errors": []}

    async def _fake_submit(draft_data: dict):  # noqa: ARG001
        calls.append("submit")
        return {"status": "SUBMITTED"}

    monkeypatch.setattr(researcher, "draft_workchain_builder", _fake_draft)
    monkeypatch.setattr(researcher, "validate_job", _fake_validate)
    monkeypatch.setattr(researcher, "submit_job", _fake_submit)

    result = await researcher.submit_new_workflow(
        _ctx(),
        workchain="quantumespresso.pw.base",
        structure_pk=11,
        code="pw@localhost",
    )

    assert result["status"] == "SUBMISSION_DRAFT"
    assert result["validation_summary"]["is_valid"] is True
    assert result["submission_draft"]["process_label"] == "quantumespresso.pw.base"
    assert isinstance(result["submission_draft"]["primary_inputs"], dict)
    assert isinstance(result["submission_draft"]["advanced_settings"], dict)
    assert isinstance(result["submission_draft"]["meta"]["pk_map"], list)
    assert str(result["submission_draft_tag"]).startswith("[SUBMISSION_DRAFT]")
    assert "summary_text" in result["validation_summary"]
    assert calls == ["draft", "validate"]


@pytest.mark.anyio
async def test_submit_new_workflow_retries_with_pseudodojo_when_sssp_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_calls: list[dict | None] = []
    validate_calls = 0

    async def _fake_draft(
        workchain: str,
        structure_pk: int,
        code: str,
        protocol: str,
        overrides: dict | None = None,
    ):
        draft_calls.append(overrides)
        assert workchain == "quantumespresso.pw.base"
        assert structure_pk == 19
        assert code == "pw@localhost"
        assert protocol == "moderate"
        if overrides is None:
            return {"status": "ERROR", "error": "SSSP pseudo family not found"}
        assert overrides.get("pseudo_family") == "PseudoDojo"
        return {
            "status": "DRAFT_READY",
            "builder": {"workchain": workchain, "pseudo_family": "PseudoDojo"},
        }

    async def _fake_validate(draft_data: dict):
        nonlocal validate_calls
        validate_calls += 1
        assert draft_data.get("status") == "DRAFT_READY"
        return {"status": "VALIDATION_OK", "errors": [], "warnings": []}

    monkeypatch.setattr(researcher, "draft_workchain_builder", _fake_draft)
    monkeypatch.setattr(researcher, "validate_job", _fake_validate)

    result = await researcher.submit_new_workflow(
        _ctx(),
        workchain="quantumespresso.pw.base",
        structure_pk=19,
        code="pw@localhost",
    )

    assert result["status"] == "SUBMISSION_DRAFT"
    assert validate_calls == 1
    assert len(draft_calls) == 2
    assert draft_calls[0] is None
    assert isinstance(draft_calls[1], dict)
    assert draft_calls[1]["pseudo_family"] == "PseudoDojo"


@pytest.mark.anyio
async def test_submit_validated_workflow_blocks_invalid_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_draft(workchain: str, structure_pk: int, code: str, protocol: str):  # noqa: ARG001
        return {"status": "DRAFT_READY", "builder": {"workchain": workchain}}

    async def _fake_validate(draft_data: dict):  # noqa: ARG001
        return {"status": "VALIDATION_FAILED", "errors": ["Missing required pseudo family"]}

    async def _fake_submit(draft_data: dict):  # noqa: ARG001
        raise AssertionError("submit_job should not be called for invalid validation")

    monkeypatch.setattr(researcher, "draft_workchain_builder", _fake_draft)
    monkeypatch.setattr(researcher, "validate_job", _fake_validate)
    monkeypatch.setattr(researcher, "submit_job", _fake_submit)

    ctx = _ctx()
    await researcher.submit_new_workflow(
        ctx,
        workchain="quantumespresso.pw.base",
        structure_pk=11,
        code="pw@localhost",
    )
    result = await researcher.submit_validated_workflow(ctx)

    assert "error" in result
    assert "blocking issues" in result["error"]
    assert result["validation_summary"]["is_valid"] is False


@pytest.mark.anyio
async def test_submit_validated_workflow_submits_and_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_draft(workchain: str, structure_pk: int, code: str, protocol: str):  # noqa: ARG001
        return {"status": "DRAFT_READY", "builder": {"workchain": workchain}}

    async def _fake_validate(draft_data: dict):  # noqa: ARG001
        return {"status": "VALIDATION_OK", "warnings": []}

    async def _fake_submit(draft_data: dict):
        assert draft_data.get("status") == "DRAFT_READY"
        return {"status": "SUBMITTED", "job_id": 987}

    monkeypatch.setattr(researcher, "draft_workchain_builder", _fake_draft)
    monkeypatch.setattr(researcher, "validate_job", _fake_validate)
    monkeypatch.setattr(researcher, "submit_job", _fake_submit)

    ctx = _ctx()
    await researcher.submit_new_workflow(
        ctx,
        workchain="quantumespresso.pw.base",
        structure_pk=11,
        code="pw@localhost",
    )

    submitted = await researcher.submit_validated_workflow(ctx)
    assert submitted["status"] == "SUBMITTED"
    assert submitted["submission"]["job_id"] == 987

    second_attempt = await researcher.submit_validated_workflow(ctx)
    assert "error" in second_attempt
    assert "No validated workflow" in second_attempt["error"]


@pytest.mark.anyio
async def test_run_aiida_code_script_adds_recovery_hint_on_missing_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_run_python_code(
        script: str,  # noqa: ARG001
        *,
        intent: str | None = None,  # noqa: ARG001
        nodes_involved: list[int] | None = None,  # noqa: ARG001
        turn_id: int | None = None,  # noqa: ARG001
    ):
        return {
            "error": "ModuleNotFoundError: No module named 'aiida_pseudo.data.family'",
            "missing_module": "aiida_pseudo.data.family",
            "output": "",
        }

    monkeypatch.setattr(researcher, "run_python_code", _fake_run_python_code)
    ctx = _ctx()
    result = await researcher.run_aiida_code_script(
        ctx,
        script="print('test')",
        intent="test",
        nodes_involved=[264],
    )

    assert isinstance(result, dict)
    assert result["missing_module"] == "aiida_pseudo.data.family"
    assert "submit_new_workflow" in result["recovery_suggestion"]
