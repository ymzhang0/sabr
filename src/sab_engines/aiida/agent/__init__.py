from __future__ import annotations

from typing import Any

__all__ = ["aiida_researcher"]


def __getattr__(name: str) -> Any:
    if name == "aiida_researcher":
        from .researcher import aiida_researcher

        return aiida_researcher
    raise AttributeError(name)
