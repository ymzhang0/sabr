"""Compatibility wrapper for calculation inspection via unified process endpoint."""

from __future__ import annotations

from typing import Any

from .process import inspect_process


async def inspect_calculation(identifier: int | str) -> dict[str, Any] | str:
    """Inspect a calculation by delegating to `inspect_process` and returning its `calculation` section."""
    result = await inspect_process(str(identifier))
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        calculation = result.get("calculation")
        return calculation if isinstance(calculation, dict) else result
    return {"result": result}
