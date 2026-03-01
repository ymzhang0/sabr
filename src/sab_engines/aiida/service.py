"""Canonical AiiDA service facade.

Aggregates worker-backed hub state and frontend helper accessors.
"""

from .frontend_bridge import (
    add_nodes_to_group,
    create_group,
    delete_group,
    export_group,
    get_context_nodes,
    get_recent_nodes,
    get_recent_processes,
    list_groups,
    list_group_labels,
    rename_group,
    soft_delete_node,
)
from .hub import AiiDAHub, hub

__all__ = [
    "AiiDAHub",
    "hub",
    "add_nodes_to_group",
    "create_group",
    "delete_group",
    "export_group",
    "get_context_nodes",
    "get_recent_nodes",
    "get_recent_processes",
    "list_groups",
    "list_group_labels",
    "rename_group",
    "soft_delete_node",
]
