"""Observation model: structured input from the environment for the Brain."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Observation(BaseModel):
    """
    Immutable snapshot of what the agent perceives at a given moment.

    Serves as the standard contract between Perceptor and Brain.
    Use raw for a textual summary and features for structured data (e.g. CPU percentages).
    """

    raw: str = Field(
        ...,
        description="Primary textual or serialized representation of the observation.",
    )
    source: str = Field(
        default="default",
        description="Identifier of the perception source (e.g. sensor, API, user).",
    )
    features: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data from the environment (e.g. cpu_usage_percent, metrics).",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this observation was captured.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional extra context (e.g. confidence, tags).",
    )
