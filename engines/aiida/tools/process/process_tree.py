"""Legacy placeholder: provenance trees are now generated server-side in aiida-worker."""

from __future__ import annotations

from typing import Any


class ProcessTree:
    """Thin compatibility shim kept to avoid import breakage in older code paths."""

    def __init__(self, node: Any, name: str = "ROOT") -> None:  # noqa: ANN401
        self.node = node
        self.name = name

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "ProcessTree construction moved to aiida-worker `/process/{identifier}`.",
            "name": self.name,
        }

    def print_tree(self, prefix: str = "", is_last: bool = True) -> None:  # noqa: ARG002
        print(f"{prefix}ProcessTree is now provided by aiida-worker.")
