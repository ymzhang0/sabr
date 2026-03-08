"""Tests for AiiDA bridge status refresh compatibility behavior."""

import asyncio

import httpx

from src.aris_apps.aiida.bridge_service import AiiDABridgeService


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


def test_refresh_legacy_plugins_fallback_to_submission_plugins() -> None:
    service = AiiDABridgeService(bridge_url="http://127.0.0.1:8001")

    async def fake_fetch_json(path: str, *, timeout_seconds: float | None = None) -> object:
        _ = timeout_seconds
        if path == "/status":
            request = httpx.Request("GET", "http://127.0.0.1:8001/status")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("Not Found", request=request, response=response)
        if path == "/plugins":
            request = httpx.Request("GET", "http://127.0.0.1:8001/plugins")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("Not Found", request=request, response=response)
        if path == "/submission/plugins":
            return ["quantumespresso.pw.relax", "quantumespresso.pw.base"]
        if path == "/system/info":
            return {
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 2, "workchains": 0},
            }
        if path == "/resources":
            return {"computers": [{"label": "localhost"}], "codes": [{"label": "pw"}]}
        raise AssertionError(f"Unexpected path: {path}")

    service._fetch_json = fake_fetch_json  # type: ignore[method-assign]

    snapshot = asyncio.run(service.get_status(force_refresh=True))

    assert snapshot.status == "online"
    assert snapshot.plugins == ["quantumespresso.pw.base", "quantumespresso.pw.relax"]
    assert snapshot.resources.workchains == 2


def test_refresh_status_without_plugins_backfills_from_submission_plugins() -> None:
    service = AiiDABridgeService(bridge_url="http://127.0.0.1:8001")

    async def fake_fetch_json(path: str, *, timeout_seconds: float | None = None) -> object:
        _ = timeout_seconds
        if path == "/status":
            return {
                "status": "online",
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 1, "workchains": 0},
                "plugins": [],
            }
        if path == "/plugins":
            request = httpx.Request("GET", "http://127.0.0.1:8001/plugins")
            response = httpx.Response(404, request=request)
            raise httpx.HTTPStatusError("Not Found", request=request, response=response)
        if path == "/submission/plugins":
            return ["quantumespresso.pw.relax"]
        raise AssertionError(f"Unexpected path: {path}")

    service._fetch_json = fake_fetch_json  # type: ignore[method-assign]

    snapshot = asyncio.run(service.get_status(force_refresh=True))

    assert snapshot.status == "online"
    assert snapshot.plugins == ["quantumespresso.pw.relax"]
    assert snapshot.resources.workchains == 1


def test_refresh_backfills_plugins_from_workchains_payload_shape() -> None:
    async def fake_fetch_json(path: str, **_: object) -> object:
        if path == "/status":
            return {
                "status": "online",
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 1, "workchains": 0},
                "plugins": [],
            }
        if path == "/plugins":
            request = httpx.Request("GET", "http://127.0.0.1:8001/plugins")
            response = httpx.Response(status_code=404, request=request, json={"detail": "missing"})
            raise httpx.HTTPStatusError("Not found", request=request, response=response)
        if path == "/submission/plugins":
            return {"workchains": [{"entry_point": "quantumespresso.pw.relax"}]}
        raise AssertionError(f"Unexpected path: {path}")

    service = AiiDABridgeService(bridge_url="http://127.0.0.1:8001")
    service._fetch_json = fake_fetch_json  # type: ignore[method-assign]

    snapshot = asyncio.run(service.get_status(force_refresh=True))

    assert snapshot.status == "online"
    assert snapshot.plugins == ["quantumespresso.pw.relax"]
    assert snapshot.resources.workchains == 1


def test_refresh_backfills_plugins_from_mapping_payload_shape() -> None:
    async def fake_fetch_json(path: str, **_: object) -> object:
        if path == "/status":
            return {
                "status": "online",
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 1, "workchains": 0},
                "plugins": [],
            }
        if path == "/plugins":
            request = httpx.Request("GET", "http://127.0.0.1:8001/plugins")
            response = httpx.Response(status_code=404, request=request, json={"detail": "missing"})
            raise httpx.HTTPStatusError("Not found", request=request, response=response)
        if path == "/submission/plugins":
            return {
                "quantumespresso.pw.base": {"label": "PW base"},
                "quantumespresso.pw.relax": {"label": "PW relax"},
            }
        raise AssertionError(f"Unexpected path: {path}")

    service = AiiDABridgeService(bridge_url="http://127.0.0.1:8001")
    service._fetch_json = fake_fetch_json  # type: ignore[method-assign]

    snapshot = asyncio.run(service.get_status(force_refresh=True))

    assert snapshot.status == "online"
    assert snapshot.plugins == ["quantumespresso.pw.base", "quantumespresso.pw.relax"]
    assert snapshot.resources.workchains == 2


def test_get_status_refresh_not_blocked_by_other_bridge_calls() -> None:
    service = AiiDABridgeService(bridge_url="http://127.0.0.1:8001")
    calls = {"status": 0}

    async def fake_fetch_json(path: str, *, timeout_seconds: float | None = None) -> object:
        _ = timeout_seconds
        if path == "/resources":
            return {"computers": [{"label": "localhost"}], "codes": [{"label": "pw"}]}
        if path == "/status":
            calls["status"] += 1
            return {
                "status": "online",
                "profile": "default",
                "daemon_status": True,
                "counts": {"computers": 1, "codes": 1, "workchains": 1},
                "plugins": ["quantumespresso.pw.relax"],
            }
        raise AssertionError(f"Unexpected path: {path}")

    service._fetch_json = fake_fetch_json  # type: ignore[method-assign]

    # Simulate unrelated successful bridge traffic that should not satisfy status cache freshness.
    _ = asyncio.run(service.get_resources())
    snapshot = asyncio.run(service.get_status(force_refresh=False))

    assert calls["status"] == 1
    assert snapshot.status == "online"
    assert snapshot.plugins == ["quantumespresso.pw.relax"]
