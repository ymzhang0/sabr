from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AiiDAEngineSettings:
    default_bridge_url: str = os.getenv("AIIDA_DEFAULT_BRIDGE_URL", "http://127.0.0.1:8001")
    bridge_url: str = os.getenv("AIIDA_BRIDGE_URL", "")
    bridge_environment: str = os.getenv("AIIDA_BRIDGE_ENVIRONMENT", "Remote Bridge")
    offline_worker_message: str = os.getenv(
        "AIIDA_OFFLINE_WORKER_MESSAGE",
        "AiiDA Worker is offline, please ensure the bridge is running on port 8001.",
    )

    @property
    def resolved_bridge_url(self) -> str:
        raw = str(self.bridge_url or self.default_bridge_url).strip()
        return raw if raw else self.default_bridge_url


aiida_engine_settings = AiiDAEngineSettings()
