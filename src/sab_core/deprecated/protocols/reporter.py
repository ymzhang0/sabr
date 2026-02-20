"""Reporter Protocol: interface for reporting observation/action results."""

from typing import Protocol, runtime_checkable

from sab_core.schema.action import Action
from sab_core.schema.observation import Observation


@runtime_checkable
class Reporter(Protocol):
    """
    Standard interface for status reporting.
    Implementations can be a console logger, web UI, database, or Discord bot.
    """

    def emit(self, observation: Observation, action: Action) -> None:
        """Called by the engine after each perceive → decide → execute step."""
        ...
