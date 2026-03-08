from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.aris_core.schema.observation import Observation


@runtime_checkable
class Perceptor(Protocol):
    def perceive(self) -> Observation: ...


__all__ = ["Perceptor"]
