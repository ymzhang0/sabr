# src/sab_core/brain/gemini.py
import json
import os
import re
from google import genai
from google.genai import types
from sab_core.schema.action import Action
from sab_core.schema.observation import Observation
from sab_core.brain.parser import ResponseParser

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

        def clean_schema(schema: dict):
            """Recursively remove 'additionalProperties' and 'title' for Gemini API."""
            if not isinstance(schema, dict):
                return schema
            
            # Remove keys forbidden by Gemini Structured Output
            schema.pop('additionalProperties', None)
            schema.pop('title', None) # 'title' can also cause issues in some versions
            
            for key, value in schema.items():
                if isinstance(value, dict):
                    clean_schema(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            clean_schema(item)
            return schema

        try:
            # 1. 🚩 Prepare and clean the schema dictionary
            raw_schema = Action.model_json_schema()
            action_schema = clean_schema(raw_schema)

            # 🚩 KEY CHANGE: Configure for Type-Safe Structured Output
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_prompt,
                    # Optional: tools can still be used, but response_schema 
                    # enforces the text part to be valid JSON matching Action.
                    tools=self._tools, 
                    response_mime_type="application/json",
                    response_schema=action_schema, # 🚩 Directly pass the Pydantic model
                ),
            )

            # 🚩 防御性检查：检查是否有有效的候选响应
            if not response.candidates or not response.candidates[0].content.parts:
                return Action(
                    name="say", 
                    payload={"content": "⚠️ Gemini returned empty content. This might be due to safety filters."}, 
                )

            first_part = response.candidates[0].content.parts[0]

            # Strategy A: Native Function Call
            # (Gemini might still prefer Function Call parts if tools are triggered)
            if first_part.function_call:
                fc = first_part.function_call
                return Action(
                    name=fc.name,
                    payload={k: str(v) for k, v in fc.args.items()}
                )
            # Strategy B: Type-Safe Parsed Response
            # When passing a dict to response_schema, response.parsed is often a dict
            if response.parsed:
                if isinstance(response.parsed, dict):
                    return Action.model_validate(response.parsed)
                return response.parsed

            # Fallback for older SDK versions or edge cases
            raw_text = response.text or ""
            return ResponseParser.parse_response(first_part, raw_text)

        except Exception as e:
            # 🚩 不在这里 log，而是返回一个 error_reported Action
            # 让上层的 Engine 捕获到这个 Action 后去执行真正的 log 操作
            return Action(
                name="error_reported", 
                payload={"message": str(e)},
                suggestions=["Check API Status", "Simplify Request"]
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

    async def stream_decide(self, observation: Observation, history: list | None = None):
        """Streaming version of decision making."""
        contents = history or []
        current_prompt = f"Observation Source: {observation.source}\nContent: {observation.raw}"
        contents.append(types.Content(role="user", parts=[types.Part(text=current_prompt)]))

        # Prepare cleaned schema for Structured Output
        def clean_schema(schema: dict):
            if not isinstance(schema, dict): return schema
            schema.pop('additionalProperties', None)
            schema.pop('title', None)
            for v in schema.values(): clean_schema(v)
            return schema

        action_schema = clean_schema(Action.model_json_schema())

        # 🚩 Use generate_content_stream for token streaming
        async for chunk in await self._client.aio.models.generate_content_stream(
            model=self._model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self._system_prompt,
                tools=self._tools,
                response_mime_type="application/json",
                response_schema=action_schema,
            ),
        ):
            # If the chunk has a function call, we usually don't stream text
            if chunk.candidates[0].content.parts[0].function_call:
                yield chunk.candidates[0].content.parts[0].function_call
                return

            # Yield the text fragments
            yield chunk.text