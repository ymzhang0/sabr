from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class SABRResponse(BaseModel):
    answer: str = Field(description="Natural language summary of the result.")
    thought_process: List[str] = Field(description="Step-by-step logic summary.")
    data_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw data resulting from tool calls.",
    )
    is_successful: bool = Field(default=True)
    suggestions: List[str] = Field(
        default_factory=list,
        description="Actionable next steps for the user. Each must be < 5 words.",
    )

    @field_validator("suggestions")
    @classmethod
    def validate_suggestions(cls, value: List[str]) -> List[str]:
        for item in value:
            word_count = len(item.split())
            if word_count > 5:
                raise ValueError(
                    f"Suggestion '{item}' is too long ({word_count} words). "
                    "Keep it under 5 words for UI compatibility."
                )
        return value


__all__ = ["SABRResponse"]
