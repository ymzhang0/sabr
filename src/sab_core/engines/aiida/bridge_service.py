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
class BridgeResourceCounts:
    computers: int = 0
    codes: int = 0
    workchains: int = 0


@dataclass
class BridgeSnapshot:
    status: BridgeConnectionState = "offline"
    url: str = "http://127.0.0.1:8001"
    environment: str = "Remote Bridge"
    profile: str = "unknown"
    daemon_status: bool = False
    resources: BridgeResourceCounts = field(default_factory=BridgeResourceCounts)
    plugins: list[str] = field(default_factory=list)
    checked_at: float = 0.0


class AiiDABridgeService:
    def __init__(
        self,
        bridge_url: str,
        *,
        environment: str = "Remote Bridge",
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
            profile=self._snapshot.profile,
            daemon_status=self._snapshot.daemon_status,
            resources=BridgeResourceCounts(
                computers=self._snapshot.resources.computers,
                codes=self._snapshot.resources.codes,
                workchains=self._snapshot.resources.workchains,
            ),
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

    async def get_profiles(self) -> dict[str, Any]:
        payload = await self._fetch_json(
            "/management/profiles",
            timeout_seconds=max(8.0, self._request_timeout_seconds),
        )
        if not isinstance(payload, dict):
            return {"current_profile": None, "default_profile": None, "profiles": []}
        return payload

    async def switch_profile(self, profile: str) -> dict[str, Any]:
        payload = await self._post_json(
            "/management/profiles/switch",
            payload={"profile": profile},
            timeout_seconds=max(8.0, self._request_timeout_seconds),
        )
        await self.get_status(force_refresh=True)
        if not isinstance(payload, dict):
            return {"status": "switched", "current_profile": profile}
        return payload

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

        status_error: Exception | None = None
        try:
            payload = await self._fetch_json("/status")
        except Exception as exc:  # noqa: BLE001
            status_error = exc
            payload = await self._fetch_legacy_status_payload()
            if payload is None:
                self._snapshot.status = "offline"
                self._snapshot.checked_at = checked_at
                error_message = f"{type(exc).__name__}: {exc}"
                print(f"ERROR: Failed to fetch bridge status from {self._bridge_url} -> {error_message}")
                logger.error(
                    log_event("aiida.bridge.unreachable", url=self._bridge_url, error=error_message)
                )
                return

        normalized = self._normalize_status_payload(payload)
        self._snapshot.status = normalized["status"]
        self._snapshot.environment = normalized["environment"]
        self._snapshot.profile = normalized["profile"]
        self._snapshot.daemon_status = normalized["daemon_status"]
        self._snapshot.resources = normalized["resources"]
        self._snapshot.plugins = normalized["plugins"]
        self._snapshot.checked_at = checked_at

        if status_error is not None:
            logger.warning(
                log_event(
                    "aiida.bridge.status.fallback",
                    url=self._bridge_url,
                    error=f"{type(status_error).__name__}: {status_error}",
                )
            )

        if not self._logged_first_handshake:
            logger.info(f"[AiiDA Bridge] Connected to worker at {self._worker_target}")
            self._logged_first_handshake = True

    async def _fetch_plugins(self) -> list[str]:
        status = await self.get_status()
        return status.plugins

    async def _fetch_json(self, path: str, *, timeout_seconds: float | None = None) -> Any:
        endpoint = f"{self._bridge_url}{path}"
        timeout = httpx.Timeout(timeout_seconds or self._request_timeout_seconds)
        # Keep local bridge probing independent from env proxy settings.
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(endpoint)
            response.raise_for_status()
            return response.json()

    async def _post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        endpoint = f"{self._bridge_url}{path}"
        timeout = httpx.Timeout(timeout_seconds or self._request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(endpoint, json=payload or {})
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

    def _normalize_status_payload(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "status": "online",
                "environment": self._environment,
                "profile": "unknown",
                "daemon_status": False,
                "resources": BridgeResourceCounts(),
                "plugins": [],
            }

        raw_status = str(payload.get("status") or "online").strip().lower()
        status: BridgeConnectionState = "offline" if raw_status in {
            "offline",
            "error",
            "failed",
            "unavailable",
        } else "online"

        environment = self._extract_first_non_empty(payload, ("environment", "worker_environment"))
        profile = self._extract_profile(payload)
        daemon_status = self._extract_daemon_status(payload)
        resources = self._extract_resource_counts(payload)
        plugins = self._extract_plugins(payload)

        return {
            "status": status,
            "environment": environment or self._environment,
            "profile": profile or "unknown",
            "daemon_status": daemon_status,
            "resources": resources,
            "plugins": plugins,
        }

    async def _fetch_legacy_status_payload(self) -> dict[str, Any] | None:
        plugins_result, system_result, resources_result = await asyncio.gather(
            self._fetch_json("/plugins"),
            self._fetch_json("/system/info"),
            self._fetch_json("/resources"),
            return_exceptions=True,
        )

        any_success = not all(
            isinstance(item, Exception)
            for item in (plugins_result, system_result, resources_result)
        )
        if not any_success:
            return None

        payload: dict[str, Any] = {"status": "online"}

        if not isinstance(plugins_result, Exception):
            payload["plugins"] = plugins_result

        if isinstance(system_result, dict):
            payload["profile"] = system_result.get("profile")
            payload["daemon_status"] = system_result.get("daemon_status")
            counts = system_result.get("counts")
            if isinstance(counts, dict):
                payload["counts"] = counts
            environment = system_result.get("environment")
            if isinstance(environment, str) and environment.strip():
                payload["environment"] = environment.strip()

        if isinstance(resources_result, dict):
            payload["resources"] = resources_result

        return payload

    def _extract_profile(self, payload: dict[str, Any]) -> str | None:
        profile = self._extract_first_non_empty(payload, ("profile", "current_profile", "active_profile"))
        if profile:
            return profile

        system = payload.get("system")
        if isinstance(system, dict):
            nested = self._extract_first_non_empty(system, ("profile", "current_profile", "active_profile"))
            if nested:
                return nested
        return None

    def _extract_daemon_status(self, payload: dict[str, Any]) -> bool:
        for key in ("daemon_status", "daemon_running", "is_daemon_running"):
            value = payload.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"true", "yes", "on", "running"}:
                    return True
                if lowered in {"false", "no", "off", "stopped"}:
                    return False
        return False

    def _extract_resource_counts(self, payload: dict[str, Any]) -> BridgeResourceCounts:
        counts = BridgeResourceCounts()

        counts_payload = payload.get("counts")
        if isinstance(counts_payload, dict):
            counts.computers = self._coerce_non_negative_int(counts_payload.get("computers"))
            counts.codes = self._coerce_non_negative_int(counts_payload.get("codes"))
            counts.workchains = self._coerce_non_negative_int(counts_payload.get("workchains"))

        resources_payload = payload.get("resources")
        if isinstance(resources_payload, dict):
            computers = resources_payload.get("computers")
            codes = resources_payload.get("codes")
            if counts.computers == 0:
                counts.computers = self._count_resource_items(computers)
            if counts.codes == 0:
                counts.codes = self._count_resource_items(codes)

        # Some workers report workchains as plugin_count or through a list.
        if counts.workchains == 0:
            workchains = payload.get("workchains")
            counts.workchains = self._count_resource_items(workchains)
        if counts.workchains == 0:
            counts.workchains = self._coerce_non_negative_int(payload.get("plugin_count"))

        return counts

    def _extract_plugins(self, payload: dict[str, Any]) -> list[str]:
        for key in ("plugins", "plugin_names", "workchains"):
            raw = payload.get(key)
            normalized = self._normalize_plugins(raw)
            if normalized:
                return normalized

        resources_payload = payload.get("resources")
        if isinstance(resources_payload, dict):
            normalized = self._normalize_plugins(resources_payload.get("plugins"))
            if normalized:
                return normalized
        return []

    @staticmethod
    def _count_resource_items(value: Any) -> int:
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        return 0

    @staticmethod
    def _coerce_non_negative_int(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, parsed)

    @staticmethod
    def _extract_first_non_empty(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

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
