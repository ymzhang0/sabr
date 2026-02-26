from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from src.sab_core.config import settings

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8001"
OFFLINE_WORKER_MESSAGE = "AiiDA Worker is offline, please ensure the bridge is running on port 8001."


@dataclass
class BridgeAPIError(Exception):
    status_code: int
    message: str
    payload: Any

    def __str__(self) -> str:
        return f"HTTP {self.status_code}: {self.message}"


class BridgeOfflineError(Exception):
    def __str__(self) -> str:
        return OFFLINE_WORKER_MESSAGE


def bridge_url() -> str:
    raw = str(settings.AIIDA_BRIDGE_URL or DEFAULT_BRIDGE_URL).strip()
    return raw.rstrip("/")


def bridge_endpoint(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{bridge_url()}{normalized}"


def _extract_error_payload(response: httpx.Response) -> tuple[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            message = str(detail.get("error") or detail.get("message") or response.reason_phrase)
        else:
            message = str(payload.get("error") or payload.get("message") or response.reason_phrase)
    else:
        message = str(payload or response.reason_phrase)

    return message, payload


async def request_json(
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    json: Mapping[str, Any] | None = None,
    timeout: float = 10.0,
) -> Any:
    endpoint = bridge_endpoint(path)

    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.request(method.upper(), endpoint, params=params, json=json)
    except httpx.ConnectError as exc:
        raise BridgeOfflineError() from exc
    except httpx.RequestError as exc:
        raise BridgeAPIError(status_code=0, message=str(exc), payload={"error": str(exc)}) from exc

    if response.status_code >= 400:
        message, payload = _extract_error_payload(response)
        raise BridgeAPIError(status_code=response.status_code, message=message, payload=payload)

    try:
        return response.json()
    except ValueError as exc:
        raise BridgeAPIError(status_code=response.status_code, message="Invalid JSON response", payload=response.text) from exc


def request_json_sync(
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    json: Mapping[str, Any] | None = None,
    timeout: float = 10.0,
) -> Any:
    endpoint = bridge_endpoint(path)

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.request(method.upper(), endpoint, params=params, json=json)
    except httpx.ConnectError as exc:
        raise BridgeOfflineError() from exc
    except httpx.RequestError as exc:
        raise BridgeAPIError(status_code=0, message=str(exc), payload={"error": str(exc)}) from exc

    if response.status_code >= 400:
        message, payload = _extract_error_payload(response)
        raise BridgeAPIError(status_code=response.status_code, message=message, payload=payload)

    try:
        return response.json()
    except ValueError as exc:
        raise BridgeAPIError(status_code=response.status_code, message="Invalid JSON response", payload=response.text) from exc


def format_bridge_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, BridgeOfflineError):
        return {"error": OFFLINE_WORKER_MESSAGE}
    if isinstance(exc, BridgeAPIError):
        return {
            "error": exc.message,
            "status_code": exc.status_code,
            "details": exc.payload,
        }
    return {"error": str(exc)}
