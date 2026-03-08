"""Legacy UI compatibility surface for the AiiDA app."""

from .legacy_nicegui import RemoteAiiDAController, THEMES, create_aiida_layout

__all__ = ["RemoteAiiDAController", "THEMES", "create_aiida_layout"]
