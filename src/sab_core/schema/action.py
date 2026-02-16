"""Action model: structured output from the Brain for the Executor."""

from pydantic import BaseModel, ConfigDict, Field


class Action(BaseModel):
    """
    Standard contract for actions.
    'extra="forbid"' is required for Gemini Structured Output compatibility.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="The name of the action to take.")

    payload: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value pairs of parameters. All values should be strings.",
    )
