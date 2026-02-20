# src/sab_core/memory/json_memory.py
import json
import os
from typing import List, Dict, Any
from ..protocols.memory import Memory

class JSONMemory(Memory):
    """
    Persistent memory implementation using JSON files.
    Supports long-term summarization and tiered context retrieval.
    """
    def __init__(self, storage_dir: str, namespace: str = "default"):
        self.path = os.path.join(storage_dir, f"history_{namespace}.json")
        os.makedirs(storage_dir, exist_ok=True)
        self.data = self._load_full_dict()

    @property
    def action_history(self) -> List[Dict]:
        """Get the intermediate action history list."""
        return self.data.setdefault("action_history", [])

    @property
    def turns(self) -> List[Dict]:
        """
        Getter for dialogue turns. 
        Ensures the return value is always a list to support slicing.
        """
        if "turns" not in self.data or not isinstance(self.data["turns"], list):
            self.data["turns"] = []
        return self.data["turns"]

    @turns.setter
    def turns(self, value: List[Dict]):
        """Setter for dialogue turns."""
        if not isinstance(value, list):
            value = []
        self.data["turns"] = value

    def _load_full_dict(self) -> Dict:
        """Load the JSON file and ensure it follows the dictionary structure."""
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                try:
                    content = json.load(f)
                    if isinstance(content, dict):
                        # Ensure essential keys are present for summarization
                        content.setdefault("turns", [])
                        content.setdefault("summary", "")
                        content.setdefault("action_history", [])
                        return content
                    # Compatibility for old list-only format
                    return {"turns": content, "summary": "", "action_history": []}
                except json.JSONDecodeError:
                    pass
        return {"turns": [], "summary": "", "action_history": []}

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        # Initialize with 'summary' field for long-term storage
        return {"summary": "", "history": [], "action_history": []}

    def _save(self):
        """Save state to disk."""
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def store(self, turn_data: Dict[str, Any]):
        """Store a final dialogue turn (Intent + Response)."""
        self.turns.append(turn_data)
        # Clear intermediate actions after a turn is finalized
        self.data["action_history"] = [] 
        self._save()

    def store_action(self, action_data: Dict[str, Any]):
        """🚩 NEW: Store intermediate tool execution details for reflection."""
        self.action_history.append(action_data)
        self._save()

    def get_action_history(self, limit: int = 5) -> str:
        """Format recent actions into a string for the Brain's context."""
        if not self.action_history:
            return ""
            
        lines = ["### Recent Technical Actions (Context for Reflection):"]
        for act in self.action_history[-limit:]:
            cmd = act.get("command", "unknown")
            status = "Success" if act.get("success") else "Failed"
            output = act.get("output_summary", "")
            lines.append(f"- Executed: `{cmd}` | Status: {status} | Result: {output}")
        return "\n".join(lines)

    def get_context(self, limit: int = 10) -> List[Any]:
        """Combine global summary with recent history for context injection."""
        context = []
        if self.data.get("summary"):
            context.append({"role": "user", "parts": [{"text": f"SYSTEM RECAP: {self.data['summary']}"}]})
            context.append({"role": "model", "parts": [{"text": "Understood."}]})
            
        recent = self.turns[-(limit * 2):] if self.turns else []
        for turn in recent:
            context.append({"role": "user", "parts": [{"text": turn['intent']}]})
            if 'response' in turn:
                context.append({"role": "model", "parts": [{"text": turn['response']}]})
        return context
 
    def update_summary(self, new_summary: str, pruned_history: List[Any]):
        """Overwrite the old summary and update the remaining history."""
        self.data["summary"] = new_summary
        self.data["history"] = pruned_history
        self._save()

    def set_kv(self, key: str, value: Any):
        self.data[key] = value
        self._save()

    def get_raw_data(self, key: str):
        return self.data.get(key)

    def clear(self):
        self.data = {"turns": [], "summary": "", "action_history": []}
        if os.path.exists(self.path):
            os.remove(self.path)
