# src/sab_core/protocols/controller.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseController(ABC):
    """
    SABR v2 Logic Controller Base Class.
    Responsible for orchestrating interactions between the Agent Bus and UI components.
    """
    def __init__(self, engine: Any, components: Dict[str, Any]):
        self.engine = engine
        self.components = components

    @abstractmethod
    async def handle_send(self, text: Optional[str] = None):
        """Standard flow for processing user messages."""
        pass

    @abstractmethod
    async def switch_context(self, context_id: str):
        """Standard flow for switching environments (Archives/Profiles)."""
        pass

    def update_ui_component(self, key: str, value: Any, method: str = None):
        """
        Updates a UI component. Calls a method if specified, 
        otherwise attempts to set common attributes like .value or .text.
        """
        if key in self.components:
            component = self.components[key]
            if method and hasattr(component, method):
                getattr(component, method)(value)
            else:
                # Compatibility for NiceGUI common attributes
                if hasattr(component, 'set_text') and isinstance(value, str):
                    component.set_text(value)
                elif hasattr(component, 'value'):
                    component.value = value