from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import httpx

from src.sab_engines.aiida.config import aiida_engine_settings

DEFAULT_BRIDGE_URL = aiida_engine_settings.default_bridge_url
OFFLINE_WORKER_MESSAGE = aiida_engine_settings.offline_worker_message
BridgeCallListener = Callable[[str], None]
_bridge_call_listener: contextvars.ContextVar[BridgeCallListener | None] = contextvars.ContextVar(
    "aiida_bridge_call_listener",
    default=None,
)


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
    raw = str(aiida_engine_settings.resolved_bridge_url or DEFAULT_BRIDGE_URL).strip()
    return raw.rstrip("/")


def bridge_endpoint(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{bridge_url()}{normalized}"


def _is_identifier_segment(segment: str) -> bool:
    cleaned = segment.strip().lower()
    if not cleaned:
        return False
    if cleaned.isdigit():
        return True
    if len(cleaned) >= 8 and all(char in "0123456789abcdef-" for char in cleaned):
        return True
    return False


def _infer_bridge_call_name(method: str, path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part]
    normalized_parts = ["{id}" if _is_identifier_segment(part) else part for part in parts]
    compact = ".".join(normalized_parts[-3:]) if normalized_parts else "root"
    return f"{method.upper()} {compact}"


def _emit_bridge_call_event(method: str, path: str) -> None:
    listener = _bridge_call_listener.get()
    if listener is None:
        return
    try:
        listener(_infer_bridge_call_name(method, path))
    except Exception:  # noqa: BLE001
        # Listener errors should never block bridge calls.
        pass


def set_bridge_call_listener(
    listener: BridgeCallListener | None,
) -> contextvars.Token[BridgeCallListener | None]:
    return _bridge_call_listener.set(listener)


def reset_bridge_call_listener(token: contextvars.Token[BridgeCallListener | None]) -> None:
    _bridge_call_listener.reset(token)


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
    _emit_bridge_call_event(method, path)

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
    _emit_bridge_call_event(method, path)

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
