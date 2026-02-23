"""Tests for schema models."""

from sab_core.schema.observation import Observation
from sab_core.schema.action import Action


def test_observation_minimal() -> None:
    obs = Observation(raw="Hello, world.")
    assert obs.raw == "Hello, world."
    assert obs.source == "default"
    assert obs.metadata == {}


def test_observation_full() -> None:
    obs = Observation(
        raw="Sensor reading: 42",
        source="sensor_1",
        metadata={"unit": "celsius"},
    )
    assert obs.raw == "Sensor reading: 42"
    assert obs.source == "sensor_1"
    assert obs.metadata["unit"] == "celsius"


def test_action_minimal() -> None:
    act = Action(name="reply")
    assert act.name == "reply"
    assert act.payload == {}
    assert act.metadata == {}


def test_action_with_payload() -> None:
    act = Action(name="call_tool", payload={"arg": "value"})
    assert act.name == "call_tool"
    assert act.payload["arg"] == "value"
