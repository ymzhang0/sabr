"""Tests for AiiDA bridge status refresh compatibility behavior."""

import asyncio

import httpx

from src.sab_engines.aiida.bridge_service import AiiDABridgeService


def test_refresh_avoids_repeated_missing_status_probe() -> None:
    service = AiiDABridgeService(bridge_url="http://127.0.0.1:8001")
    calls = {"status": 0}

    async def fake_fetch_json(path: str, *, timeout_seconds: float | None = None) -> object:
        _ = timeout_seconds
        if path == "/status":
            calls["status"] += 1
            request = httpx.Request("GET", "http://127.0.0.1:8001/status")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("Not Found", request=request, response=response)
        if path == "/plugins":
            return ["demo.workchain", "a.b"]
        if path == "/system/info":
            return {
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 2, "workchains": 2},
            }
        if path == "/resources":
            return {
                "computers": [{"label": "localhost"}],
                "codes": [{"label": "pw"}, {"label": "cp"}],
            }
        raise AssertionError(f"Unexpected path: {path}")

    service._fetch_json = fake_fetch_json  # type: ignore[method-assign]

    first = asyncio.run(service.get_status(force_refresh=True))
    second = asyncio.run(service.get_status(force_refresh=True))

    assert calls["status"] == 1
    assert service._status_endpoint_supported is False
    assert first.status == "online"
    assert second.status == "online"
    assert first.profile == "default"
    assert first.daemon_status is True
    assert first.resources.computers == 1
    assert first.resources.codes == 2
    assert first.resources.workchains == 2
    assert first.plugins == ["a.b", "demo.workchain"]
