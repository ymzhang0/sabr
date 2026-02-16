"""
sab-core: Standard Agent Bus.

A lightweight, decoupled foundational library for AI Agents using Gemini as the brain.
Interface-first design: Perception → Decision (Brain) → Execution.
"""

from sab_core.brain import GeminiBrain
from sab_core.engine import SABEngine

__version__ = "0.1.0"
__all__ = ["GeminiBrain", "SABEngine"]
