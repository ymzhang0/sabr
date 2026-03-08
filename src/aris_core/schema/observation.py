from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class Observation(BaseModel):
    raw: str
    source: str = "default"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    features: Dict[str, Any] = Field(default_factory=dict)


__all__ = ["Observation"]
