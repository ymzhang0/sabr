# src/sab_core/brain/gemini.py
import json
import os
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

    async def decide(self, observation: Observation) -> Action:
        """
        自动解析 Gemini 的决策：是调用工具还是回复文字。
        """
        # 将观察结果传给 Gemini
        contents = [f"Observation Source: {observation.source}\nContent: {observation.raw}"]
        
        try:
            response = await self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_prompt,
                    tools=self._tools, # 注入工具集
                ),
            )

            # 1. 检查是否有函数调用 (Function Call)
            # Gemini 可能会同时返回多个调用，我们这里取第一个
            if response.candidates[0].content.parts[0].function_call:
                fc = response.candidates[0].content.parts[0].function_call
                # 将函数名和参数转化为 SAB Action
                # fc.args 是一个字典，我们将其转为 payload
                return Action(
                    name=fc.name,
                    payload={k: str(v) for k, v in fc.args.items()}
                )

            # 2. 如果只是普通文字回复
            text = response.text or "I'm not sure what to do next."
            return Action(name="say", payload={"content": text})

        except Exception as e:
            return Action(name="error_reported", payload={"message": str(e)})