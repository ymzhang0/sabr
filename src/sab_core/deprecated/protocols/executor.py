"""Executor Protocol: abstract interface for executing actions."""

from typing import Any, Protocol, runtime_checkable

from sab_core.schema.action import Action


@runtime_checkable
class Executor(Protocol):
    """
    Interface for components that execute actions produced by the Brain.

    Implement this protocol to plug in tools, APIs, or side effects.
    Keeps execution decoupled from perception and decision.
    """

    def execute(self, action: Action) -> Any:
        """
        Execute the given action and return a result (or None).

        Args:
            action: The Action produced by the Brain.

        Returns:
            Result of execution (e.g. tool output, status). Interpretation
            is up to the caller; can be fed back as observation in the next step.
        """
        ...
