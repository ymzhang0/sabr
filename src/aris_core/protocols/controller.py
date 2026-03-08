from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseController(ABC):
    """
    Base controller shared by legacy UI layers while platform code migrates.
    """

    def __init__(self, engine: Any, components: Dict[str, Any]):
        self.engine = engine
        self.components = components

    @abstractmethod
    async def handle_send(self, text: Optional[str] = None):
        pass

    @abstractmethod
    async def switch_context(self, context_id: str):
        pass

    def update_ui_component(self, key: str, value: Any, method: str | None = None):
        if key not in self.components:
            return

        component = self.components[key]
        if method and hasattr(component, method):
            getattr(component, method)(value)
            return

        if hasattr(component, "set_text") and isinstance(value, str):
            component.set_text(value)
        elif hasattr(component, "value"):
            component.value = value
