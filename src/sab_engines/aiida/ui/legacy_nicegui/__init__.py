"""Legacy NiceGUI implementation package."""

from .controller import RemoteAiiDAController
from .layout import create_aiida_layout
from .themes import THEMES

__all__ = ["RemoteAiiDAController", "create_aiida_layout", "THEMES"]

