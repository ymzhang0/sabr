# src/sab_core/brain/parser.py
import json
import re
import logging
from typing import Any, List, Optional
try:
    import json_repair # Use json_repair to handle malformed JSON
except ImportError:
    json_repair = None

from sab_core.schema.action import Action

class ResponseParser:
    """
    Parser for LLM responses with multiple strategies: 
    Function Call, JSON Repair, and Regex Fallback.
    """
    
    @classmethod
    def parse_response(cls, response_part: Any, raw_text: str) -> Action:
        """
        Unified entry point to parse various LLM response formats.
        """
        # Strategy 1: Native Function Call mapping
        if hasattr(response_part, "function_call") and response_part.function_call:
            return cls._from_function_call(response_part.function_call)

        # Strategy 2: Structured JSON parsing (with repair)
        parsed_json = cls._from_json(raw_text)
        if parsed_json:
            return parsed_json

        # Strategy 3: Regex Fallback for [SUGGESTIONS]: markers
        return cls._from_regex_fallback(raw_text)

    @classmethod
    def _from_function_call(cls, fc: Any) -> Action:
        """Map native Gemini function calls to Action."""
        return Action(
            name=fc.name,
            payload={k: v for k, v in fc.args.items()}
        )

    @classmethod
    def _from_json(cls, text: str) -> Optional[Action]:
        """Attempt to extract and repair JSON from raw text."""
        try:
            # Clean Markdown code blocks if present
            clean_text = re.sub(r'```json\s*|\s*```', '', text).strip()
            
            # Use json_repair if available, otherwise fallback to standard json
            if json_repair:
                data = json_repair.loads(clean_text)
            else:
                # Basic bracket extraction as a last resort before standard json.loads
                match = re.search(r'(\{.*\})', clean_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    return None

            if isinstance(data, dict):
                action_name = data.get("action", "say")
                payload = data.get("payload", {})
                
                # Normalize payload/content for AiiDA-style responses
                if action_name == "say" and "content" not in payload:
                    payload = {"content": str(data)} # Treat whole JSON as content if payload missing
                
                return Action(
                    name=action_name,
                    payload=payload,
                    suggestions=data.get("suggestions", [])
                )
        except Exception:
            return None
        return None

    @classmethod
    def _from_regex_fallback(cls, text: str) -> Action:
        """Handle plain text responses with legacy [SUGGESTIONS]: markers."""
        marker = "[SUGGESTIONS]:"
        suggestions = []
        clean_content = text
        
        if marker in text:
            parts = text.split(marker)
            clean_content = parts[0].strip()
            # Extract suggestions by comma separation
            raw_sug = parts[1].strip().split(",")
            suggestions = [s.strip().replace('"', '').replace('*', '') for s in raw_sug if s.strip()]

        return Action(
            name="say",
            payload={"content": clean_content},
            suggestions=suggestions
        )