"""Tests for Protocol compliance (Perceptor, Executor)."""

from sab_core.schema.observation import Observation
from sab_core.schema.action import Action
from sab_core.protocols.perception import Perceptor
from sab_core.protocols.executor import Executor


def test_perceptor_protocol() -> None:
    """A minimal implementation satisfies the Perceptor protocol."""

    class StubPerceptor:
        def perceive(self) -> Observation:
            return Observation(raw="stub")

    stub = StubPerceptor()
    assert isinstance(stub, Perceptor)
    obs = stub.perceive()
    assert obs.raw == "stub"


def test_executor_protocol() -> None:
    """A minimal implementation satisfies the Executor protocol."""

    class StubExecutor:
        def execute(self, action: Action) -> str:
            return f"executed:{action.name}"

    stub = StubExecutor()
    assert isinstance(stub, Executor)
    result = stub.execute(Action(name="test"))
    assert result == "executed:test"
