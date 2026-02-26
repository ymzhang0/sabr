"""Compatibility wrapper for workchain provenance inspection via unified process endpoint."""

from __future__ import annotations

from typing import Any

from .process import inspect_process


async def inspect_workchain(identifier: int | str) -> dict[str, Any] | str:
    """Inspect a workchain by delegating to `inspect_process` and returning its `workchain` section."""
    result = await inspect_process(str(identifier))
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        workchain = result.get("workchain")
        return workchain if isinstance(workchain, dict) else result
    return {"result": result}
