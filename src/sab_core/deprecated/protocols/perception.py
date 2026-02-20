"""Perceptor Protocol: abstract interface for producing observations."""

from typing import Protocol, runtime_checkable

from sab_core.schema.observation import Observation


@runtime_checkable
class Perceptor(Protocol):
    """
    Interface for components that observe the environment and produce Observations.

    Implement this protocol to plug in sensors, APIs, user input, or any source
    that feeds structured observations into the Brain. Keeps perception
    decoupled from decision and execution.
    """

    def perceive(self, intent: str = None) -> Observation:
        """
        Capture the current state of the environment as an Observation.

        Returns:
            A single Observation (e.g. latest message, sensor reading).
            For streams or batches, wrap in a single Observation or implement
            a separate protocol.
        """
        ...
