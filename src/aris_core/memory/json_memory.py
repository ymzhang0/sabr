from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    intent: str
    response: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionEntry(BaseModel):
    tool_name: str
    input_args: Dict[str, Any]
    output: str
    success: bool


class SABRMemoryState(BaseModel):
    summary: str = ""
    turns: List[MemoryEntry] = Field(default_factory=list)
    action_history: List[ActionEntry] = Field(default_factory=list)
    kv_store: Dict[str, Any] = Field(default_factory=dict)


def _default_storage_path() -> str:
    try:
        from src.aris_core.config import settings

        configured = str(getattr(settings, "SABR_MEMORY_DIR", "") or "").strip()
        if configured:
            return configured
    except Exception:  # noqa: BLE001
        pass

    return str(Path.cwd() / "runtime" / "memories")


class JSONMemory:
    """
    Persistent JSON memory store shared by the current SABR codebase and the
    future ARIS layout.
    """

    def __init__(self, namespace: str = "default", storage_path: str | None = None):
        resolved_storage_path = storage_path or _default_storage_path()
        self.file_path = os.path.join(resolved_storage_path, f"history_{namespace}.json")
        os.makedirs(resolved_storage_path, exist_ok=True)
        self.state = self._load()

    def _load(self) -> SABRMemoryState:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    return SABRMemoryState.model_validate(data)
            except Exception:  # noqa: BLE001
                pass
        return SABRMemoryState()

    def save(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as handle:
            handle.write(self.state.model_dump_json(indent=2))

    def add_turn(self, intent: str, response: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        entry = MemoryEntry(intent=intent, response=response, metadata=metadata or {})
        self.state.turns.append(entry)
        self.state.action_history = []
        self.save()

    def add_action(self, tool: str, args: Dict[str, Any], output: str, success: bool = True) -> None:
        action = ActionEntry(tool_name=tool, input_args=args, output=output, success=success)
        self.state.action_history.append(action)
        self.save()

    def set_kv(self, key: str, value: Any) -> None:
        self.state.kv_store[key] = value
        self.save()

    def get_kv(self, key: str, default: Any = None) -> Any:
        return self.state.kv_store.get(key, default)

    def clear(self) -> None:
        self.state = SABRMemoryState()
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


__all__ = [
    "ActionEntry",
    "JSONMemory",
    "MemoryEntry",
    "SABRMemoryState",
]
