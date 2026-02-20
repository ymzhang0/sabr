# src/sab_core/api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class AgentRequest(BaseModel):
    """
    The schema for incoming chat requests from the frontend.
    """
    # The user's natural language input (e.g., "Calculate Band Structure for Silicon")
    intent: str = Field(..., description="The user's query or command.")
    
    # The currently selected AiiDA archive path or profile name
    context_archive: Optional[str] = Field(
        default=None, 
        description="The active AiiDA context (profile or archive path)."
    )

    # Optional: The specific model to use (if the user switches it in the UI)
    model_name: Optional[str] = Field(
        default="gemini-2.0-flash", 
        description="The AI model ID to handle this request."
    )