from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AiiDAEngineSettings:
    bridge_url: str = os.getenv("AIIDA_BRIDGE_URL", "http://127.0.0.1:8001")


aiida_engine_settings = AiiDAEngineSettings()
