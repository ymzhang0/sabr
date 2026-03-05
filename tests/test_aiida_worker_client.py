from __future__ import annotations

import pytest

from src.sab_engines.aiida.client import (
    AiiDAWorkerClient,
    aiida_worker_client,
    bridge_service,
    get_aiida_worker_client,
)


def test_worker_client_singleton_aliases_are_stable() -> None:
    first = get_aiida_worker_client()
    second = get_aiida_worker_client()
    assert first is second
    assert aiida_worker_client is first
    assert bridge_service is first


def test_worker_client_is_connected_property_tracks_status() -> None:
    client = AiiDAWorkerClient(bridge_url="http://127.0.0.1:8001")
    assert client.is_connected is False
    client._mark_online()  # noqa: SLF001
    assert client.is_connected is True
    client._mark_offline()  # noqa: SLF001
    assert client.is_connected is False


@pytest.mark.anyio
async def test_inspect_infrastructure_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AiiDAWorkerClient(
        bridge_url="http://127.0.0.1:8001",
        infra_cache_ttl_seconds=120.0,
    )
    calls: list[str] = []

    async def _fake_fetch_json(path: str, *, timeout_seconds: float | None = None, retries: int | None = None):
        _ = timeout_seconds, retries
        calls.append(path)
        if path == "/system/info":
            return {
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 2, "workchains": 3},
            }
        if path == "/resources":
            return {
                "computers": [{"label": "localhost"}],
                "codes": [{"label": "pw", "computer_label": "localhost"}],
            }
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(client, "_fetch_json", _fake_fetch_json)  # type: ignore[method-assign]

    first = await client.inspect_infrastructure()
    second = await client.inspect_infrastructure()

    assert calls == ["/system/info", "/resources"]
    assert first == second
    assert first["profile"] == "default"
    assert first["code_targets"] == ["pw@localhost"]


@pytest.mark.anyio
async def test_get_current_user_info(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AiiDAWorkerClient(bridge_url="http://127.0.0.1:8001")
    user_info = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "institution": "Test Inst",
    }

    async def _fake_fetch_json(path: str, **kwargs):
        assert path == "/management/profiles/current-user-info"
        return user_info

    monkeypatch.setattr(client, "_fetch_json", _fake_fetch_json)
    result = await client.get_current_user_info()
    assert result == user_info


@pytest.mark.anyio
async def test_setup_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AiiDAWorkerClient(bridge_url="http://127.0.0.1:8001")
    payload = {"profile_name": "new_profile"}

    async def _fake_post_json(path: str, payload: dict, **kwargs):
        assert path == "/management/profiles/setup"
        assert payload["profile_name"] == "new_profile"
        return {"status": "success", "profile_name": "new_profile"}

    monkeypatch.setattr(client, "_post_json", _fake_post_json)
    result = await client.setup_profile(payload)
    assert result["status"] == "success"
    assert result["profile_name"] == "new_profile"
