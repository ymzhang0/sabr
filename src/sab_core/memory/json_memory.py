# src/sab_core/memory/json_memory.py
import json
import os
from typing import List, Dict, Any
from ..protocols.memory import BaseMemory

class JSONMemory(BaseMemory):
    def __init__(self, storage_dir: str, namespace: str = "default"):
        self.path = os.path.join(storage_dir, f"history_{namespace}.json")
        os.makedirs(storage_dir, exist_ok=True)
        self.turns = self._load()

    def _load(self) -> List[Dict]:
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def store(self, turn_data: Dict[str, Any]):
        """
        turn_data 预期结构:
        {
            "intent": str,
            "actions": List[Dict],  # 🚩 新增：记录执行的命令和结果
            "response": str,
            "observation_snapshot": str
        }
        """
        self.turns.append(turn_data)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.turns, f, ensure_ascii=False, indent=2)

    def get_action_history(self, limit: int = 5) -> str:
        """
        🚩 特性：提取最近的操作日志，用于给 AI 做“反思”参考
        """
        history_lines = ["### Past Action Logs (Your previous technical steps):"]
        for turn in self.turns[-limit:]:
            for act in turn.get("actions", []):
                cmd = act.get("command", "unknown")
                status = "Success" if act.get("success") else "Failed"
                history_lines.append(f"- Executed: `{cmd}` | Status: {status}")
        return "\n".join(history_lines)

    def get_context(self, limit: int = 10) -> List[Dict]:
        """提取最近的回合，并格式化为对话角色格式"""
        context = []
        # 只取最后 limit * 2 条记录（一问一答算两条）
        recent_turns = self.turns[-(limit * 2):] if self.turns else []
        
        for turn in recent_turns:
            context.append({"role": "user", "parts": [{"text": turn['intent']}]})
            if 'response' in turn and turn['response']:
                context.append({"role": "model", "parts": [{"text": turn['response']}]})
        return context

    def set_kv(self, key: str, value: Any):
        """通用键值对存储"""
        data = self._load_full_dict() # 加载整个 JSON
        data[key] = value
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_raw_data(self, key: str):
        """读取特定键的值"""
        data = self._load_full_dict()
        return data.get(key)
    
    def _load_full_dict(self) -> Dict:
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                return content if isinstance(content, dict) else {"turns": content}
        return {}

    def clear(self):
        self.turns = []
        if os.path.exists(self.path):
            os.remove(self.path)