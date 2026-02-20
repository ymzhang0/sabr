import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# --- 1. Data Models for Persistence ---

class MemoryEntry(BaseModel):
    """Represents a single completed interaction turn."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    intent: str
    response: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ActionEntry(BaseModel):
    """Represents an intermediate tool execution during a cyclic loop."""
    tool_name: str
    input_args: Dict[str, Any]
    output: str
    success: bool

class SABRMemoryState(BaseModel):
    """The full schema of the JSON storage file."""
    summary: str = ""
    turns: List[MemoryEntry] = Field(default_factory=list)
    action_history: List[ActionEntry] = Field(default_factory=list)
    kv_store: Dict[str, Any] = Field(default_factory=dict)

# --- 2. Memory Implementation ---

class JSONMemory:
    """
    SABR v2 Persistent Memory.
    Uses Pydantic models for data validation and easy JSON serialization.
    """
    def __init__(self, namespace: str = "default", storage_path: str = "data/memories"):
        self.file_path = os.path.join(storage_path, f"history_{namespace}.json")
        os.makedirs(storage_path, exist_ok=True)
        self.state = self._load()

    def _load(self) -> SABRMemoryState:
        """Load data from JSON or return a fresh state."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return SABRMemoryState.model_validate(data)
            except Exception:
                pass
        return SABRMemoryState()

    def save(self):
        """Persist current state to disk."""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write(self.state.model_dump_json(indent=2))

    def add_turn(self, intent: str, response: str, metadata: Optional[Dict] = None):
        """Record a completed conversation turn."""
        entry = MemoryEntry(intent=intent, response=response, metadata=metadata or {})
        self.state.turns.append(entry)
        # Clear short-term action history after a turn is finalized
        self.state.action_history = []
        self.save()

    def add_action(self, tool: str, args: Dict, output: str, success: bool = True):
        """Record a tool execution (useful for cyclic reasoning context)."""
        action = ActionEntry(tool_name=tool, input_args=args, output=output, success=success)
        self.state.action_history.append(action)
        self.save()

    def set_kv(self, key: str, value: Any):
        """Store arbitrary key-value pairs (e.g., recent_archives)."""
        self.state.kv_store[key] = value
        self.save()

    def get_kv(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the KV store."""
        return self.state.kv_store.get(key, default)

    def clear(self):
        """Wipe memory."""
        self.state = SABRMemoryState()
        if os.path.exists(self.file_path):
            os.remove(self.file_path)