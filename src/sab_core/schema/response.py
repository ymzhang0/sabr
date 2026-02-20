from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any

class SABRResponse(BaseModel):
    """
    The structured final report from the Agent.
    Includes automated validation for UI components like suggestions.
    """
    answer: str = Field(description="Natural language summary of the result.")
    thought_process: List[str] = Field(description="Step-by-step logic summary.")
    data_payload: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Raw data resulting from tool calls."
    )
    is_successful: bool = Field(default=True)
    
    # 🚩 Enhanced Suggestions field
    suggestions: List[str] = Field(
        default_factory=list,
        description="Actionable next steps for the user. Each must be < 5 words."
    )

    @field_validator('suggestions')
    @classmethod
    def validate_suggestions(cls, v: List[str]) -> List[str]:
        """
        Ensures every suggestion is concise and actionable.
        If a suggestion is too long, PydanticAI will trigger a retry loop.
        """
        for s in v:
            word_count = len(s.split())
            if word_count > 5:
                raise ValueError(
                    f"Suggestion '{s}' is too long ({word_count} words). "
                    "Keep it under 5 words for UI compatibility."
                )
        return v