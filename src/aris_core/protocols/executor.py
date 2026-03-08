from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.aris_core.schema.action import Action


@runtime_checkable
class Executor(Protocol):
    def execute(self, action: Action) -> Any: ...


__all__ = ["Executor"]
