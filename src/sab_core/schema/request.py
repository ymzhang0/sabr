# src/sab_core/schema/request.py
from pydantic import BaseModel, Field
from typing import Optional

class AgentRequest(BaseModel):
    """
    The schema for incoming chat requests from the frontend.
    """
    # The user's natural language input (e.g., "analyze this material workflow")
    intent: str = Field(..., description="The user's query or command.")
    
    # Optional engine-specific context handle (profile/archive/project id, etc.)
    context_archive: Optional[str] = Field(
        default=None, 
        description="The active engine context identifier."
    )

    # Optional: The specific model to use (if the user switches it in the UI)
    model_name: Optional[str] = Field(
        default="gemini-2.0-flash", 
        description="The AI model ID to handle this request."
    )
