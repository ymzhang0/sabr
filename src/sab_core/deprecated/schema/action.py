"""Action model: structured output from the Brain for the Executor."""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any

class Action(BaseModel):
    """
    Standard contract for actions.
    Note: 'extra="forbid"' is removed to ensure Gemini API compatibility.
    """

    # 🚩 Remove extra="forbid" to prevent 'additionalProperties' generation
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., description="The name of the action to take.")

    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the tool. All values should be strings or numbers."
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="3 short follow-up suggestions for the user."
    )
