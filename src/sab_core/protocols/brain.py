"""Brain protocol: decision layer interface (observations in, actions out)."""

from typing import Protocol, runtime_checkable

from sab_core.schema.action import Action
from sab_core.schema.observation import Observation


@runtime_checkable
class Brain(Protocol):
    """
    Interface for the decision layer: observes in, actions out.

    Implementations typically call Gemini (or another LLM) to turn
    Observations into Actions. Keeps LLM orchestration decoupled from
    perception and execution.
    """

    def decide(self, observation: Observation, history=None) -> Action:
        """
        Produce an Action from the current Observation (e.g. via LLM).

        Args:
            observation: Current perception from the environment.

        Returns:
            The chosen Action to execute.
        """
        ...
