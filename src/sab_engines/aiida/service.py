"""Canonical AiiDA service facade.

Aggregates worker-backed hub state and frontend helper accessors.
"""

from .frontend_bridge import (
    get_context_nodes,
    get_recent_nodes,
    get_recent_processes,
    list_group_labels,
)
from .hub import AiiDAHub, hub

__all__ = [
    "AiiDAHub",
    "hub",
    "get_context_nodes",
    "get_recent_nodes",
    "get_recent_processes",
    "list_group_labels",
]
