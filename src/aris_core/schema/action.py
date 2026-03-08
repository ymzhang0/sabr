from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class Action(BaseModel):
    name: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


__all__ = ["Action"]
