from pydantic import BaseModel
from typing import List, Optional, Any

class AgentRequest(BaseModel):
    intent: str
    context_archive: Optional[str] = None

class AgentResponse(BaseModel):
    content: str            # AI 的话语
    action_name: str        # 执行的操作名
    result: Any             # AiiDA 执行的真实结果
    suggestions: List[str]  # 建议