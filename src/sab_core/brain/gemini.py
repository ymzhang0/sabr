# src/sab_core/brain/gemini.py
import json
import os
import re
from google import genai
from google.genai import types
from sab_core.schema.action import Action
from sab_core.schema.observation import Observation

class GeminiBrain:
    def __init__(self, *, model_name: str = "gemini-2.0-flash", api_key: str | None = None, 
                 system_prompt: str = "", tools: list = None, http_options: dict = None) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = genai.Client(api_key=key, http_options=http_options)
        self._model_name = model_name
        self._system_prompt = system_prompt
        # 这里的 tools 是函数引用列表
        self._tools = tools 

    async def decide(self, observation: Observation, history: list | None = None) -> Action:        
        contents = history or []
        current_prompt = f"Observation Source: {observation.source}\nContent: {observation.raw}"
        contents.append(types.Content(role="user", parts=[types.Part(text=current_prompt)]))

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_prompt,
                    tools=self._tools,
                ),
            )

            # 🚩 防御性检查：检查是否有有效的候选响应
            if not response.candidates or not response.candidates[0].content.parts:
                return Action(
                    name="say", 
                    payload={"content": "⚠️ Gemini returned empty content. This might be due to safety filters."}, 
                    suggestions=["Retry", "Rephrase request"]
                )

            first_part = response.candidates[0].content.parts[0]

            # --- 情况 A: 原生函数调用 ---
            if first_part.function_call:
                fc = first_part.function_call
                return Action(
                    name=fc.name,
                    payload={k: v for k, v in fc.args.items()}
                )

            # --- 情况 B: 文本回复 (JSON 或 标记文本) ---
            raw_text = response.text or ""
            text_content = raw_text
            suggestions = []

            # 1. 尝试解析 JSON (针对你的 EVOLUTION_PROMPT)
            try:
                clean_json_str = re.sub(r'```json\s*|\s*```', '', raw_text).strip()
                if clean_json_str.startswith('{') and clean_json_str.endswith('}'):
                    data = json.loads(clean_json_str)
                    action_name = data.get("action", "say")
                    full_payload = data.get("payload", {})
                    verbal_content = full_payload.pop("content", "")
                    suggestions = full_payload.pop("suggestions", [])
                    if action_name == "run_aiida_code" and "command" in full_payload:
                        full_payload["code"] = full_payload.pop("command")
                    # 如果是普通对话，payload 重新包装回 content
                    if action_name == "say":
                        tool_payload = {"content": verbal_content}
                    else:
                        # 如果是工具调用（如 get_statistics），此时 tool_payload 应该是空的 {}
                        # 或者只包含工具需要的参数
                        tool_payload = full_payload
                    return Action(
                        name=action_name,
                        payload=tool_payload,
                        suggestions=suggestions,
                        # 🚩 建议：如果你能给 Action 类加个 content 属性最好
                        # 如果不能改 Action 类，我们就把 content 留在日志里
                    )
            except:
                pass # 解析失败，退化到普通文本解析

            # 2. 尝试解析标记位 [SUGGESTIONS]:
            marker = "[SUGGESTIONS]:"
            if marker in text_content:
                parts = text_content.split(marker)
                text_content = parts[0].strip()
                raw_sug = parts[1].strip().split(",")
                suggestions = [s.strip().replace('"', '').replace('*', '') for s in raw_sug if s.strip()]

            return Action(
                name="say", 
                payload={"content": text_content},
                suggestions=suggestions 
            )

        except Exception as e:
            # 🚩 不在这里 log，而是返回一个 error_reported Action
            # 让上层的 Engine 捕获到这个 Action 后去执行真正的 log 操作
            return Action(
                name="error_reported", 
                payload={"message": str(e)},
                suggestions=["Check API Status", "Simplify Input"]
            )
            
    def get_available_models(self) -> list[str]:
        """
        使用新版 google-genai SDK 动态获取模型列表
        """
        try:
            available = []
            for m in self._client.models.list():
                # 新版 SDK 使用 supported_actions 属性
                if 'generateContent' in m.supported_actions:
                    name = m.name.replace('models/', '')
                    available.append(name)
            # 过滤掉 'models/' 前缀并排序
            return sorted(available, key=lambda x: ("2.0" not in x, x))
        except Exception as e:
            print(f"Failed to fetch models: {e}")
            return ['gemini-2.0-flash', 'gemini-1.5-pro']