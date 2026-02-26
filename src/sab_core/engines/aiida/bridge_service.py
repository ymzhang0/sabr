from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from loguru import logger

from src.sab_core.engines.aiida.config import aiida_engine_settings
from src.sab_core.logging_utils import log_event

BridgeConnectionState = Literal["online", "offline"]


@dataclass
class BridgeSnapshot:
    status: BridgeConnectionState = "offline"
    url: str = "http://127.0.0.1:8001"
    environment: str = "Local Sandbox"
    plugins: list[str] = field(default_factory=list)
    checked_at: float = 0.0


class AiiDABridgeService:
    def __init__(
        self,
        bridge_url: str,
        *,
        environment: str = "Local Sandbox",
        cache_ttl_seconds: float = 10.0,
        request_timeout_seconds: float = 2.0,
    ) -> None:
        normalized_url = (bridge_url or "http://127.0.0.1:8001").strip()
        self._bridge_url = normalized_url.rstrip("/")
        self._environment = environment
        self._cache_ttl_seconds = max(1.0, float(cache_ttl_seconds))
        self._request_timeout_seconds = max(0.2, float(request_timeout_seconds))
        self._snapshot = BridgeSnapshot(url=self._bridge_url, environment=self._environment)
        self._lock = asyncio.Lock()
        self._logged_first_handshake = False

    @property
    def bridge_url(self) -> str:
        return self._bridge_url

    async def get_status(self, *, force_refresh: bool = False) -> BridgeSnapshot:
        await self._refresh_if_needed(force_refresh=force_refresh)
        return BridgeSnapshot(
            status=self._snapshot.status,
            url=self._snapshot.url,
            environment=self._snapshot.environment,
            plugins=list(self._snapshot.plugins),
            checked_at=self._snapshot.checked_at,
        )

    async def get_plugins(self, *, force_refresh: bool = False) -> list[str]:
        snapshot = await self.get_status(force_refresh=force_refresh)
        return snapshot.plugins

    async def get_system_info(self) -> dict[str, Any]:
        payload = await self._fetch_json("/system/info", timeout_seconds=max(8.0, self._request_timeout_seconds))
        return payload if isinstance(payload, dict) else {}

    async def get_resources(self) -> dict[str, Any]:
        payload = await self._fetch_json("/resources", timeout_seconds=max(8.0, self._request_timeout_seconds))
        return payload if isinstance(payload, dict) else {}

    async def _refresh_if_needed(self, *, force_refresh: bool) -> None:
        if not force_refresh and self._is_cache_fresh():
            return

        async with self._lock:
            if not force_refresh and self._is_cache_fresh():
                return
            await self._refresh_locked()

    def _is_cache_fresh(self) -> bool:
        checked_at = self._snapshot.checked_at
        if checked_at <= 0:
            return False
        return (time.monotonic() - checked_at) < self._cache_ttl_seconds

    async def _refresh_locked(self) -> None:
        checked_at = time.monotonic()

        try:
            plugins = await self._fetch_plugins()
        except Exception as exc:  # noqa: BLE001
            self._snapshot.status = "offline"
            self._snapshot.checked_at = checked_at
            error_message = f"{type(exc).__name__}: {exc}"
            print(f"ERROR: Failed to fetch bridge plugins from {self._bridge_url} -> {error_message}")
            logger.error(
                log_event("aiida.bridge.unreachable", url=self._bridge_url, error=error_message)
            )
            return

        self._snapshot.status = "online"
        self._snapshot.plugins = plugins
        self._snapshot.checked_at = checked_at

        if not self._logged_first_handshake:
            logger.info(f"[AiiDA Bridge] Connected to worker at {self._worker_target}")
            self._logged_first_handshake = True

    async def _fetch_plugins(self) -> list[str]:
        print(f"DEBUG: Fetching plugins from {self._bridge_url}")
        payload = await self._fetch_json("/plugins")
        return self._normalize_plugins(payload)

    async def _fetch_json(self, path: str, *, timeout_seconds: float | None = None) -> Any:
        endpoint = f"{self._bridge_url}{path}"
        timeout = httpx.Timeout(timeout_seconds or self._request_timeout_seconds)
        # Keep local bridge probing independent from env proxy settings.
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()

    @property
    def _worker_target(self) -> str:
        parsed = urlparse(self._bridge_url)
        if parsed.port:
            return f":{parsed.port}"
        if parsed.netloc:
            return parsed.netloc
        return self._bridge_url

    def _normalize_plugins(self, payload: Any) -> list[str]:
        raw_plugins: list[Any]
        if isinstance(payload, list):
            raw_plugins = payload
        elif isinstance(payload, dict):
            plugins = payload.get("plugins")
            if isinstance(plugins, list):
                raw_plugins = plugins
            else:
                items = payload.get("items")
                raw_plugins = items if isinstance(items, list) else []
        else:
            raw_plugins = []

        normalized: list[str] = []
        seen: set[str] = set()
        for item in raw_plugins:
            plugin_name = self._normalize_plugin_item(item)
            if not plugin_name or plugin_name in seen:
                continue
            seen.add(plugin_name)
            normalized.append(plugin_name)

        normalized.sort()
        return normalized

    @staticmethod
    def _normalize_plugin_item(item: Any) -> str:
        if isinstance(item, str):
            return item.strip()

        if isinstance(item, dict):
            for key in ("name", "entry_point", "plugin", "id"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return str(item).strip()

        return str(item).strip()


bridge_service = AiiDABridgeService(bridge_url=aiida_engine_settings.bridge_url)
