from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AiiDAEngineSettings:
    bridge_url: str = os.getenv("AIIDA_BRIDGE_URL", "http://127.0.0.1:8001")
    profile_name: str = os.getenv("SABR_AIIDA_PROFILE", "default")


aiida_engine_settings = AiiDAEngineSettings()
