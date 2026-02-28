"""Canonical AiiDA worker client facade.

This module centralizes both low-level HTTP helpers and higher-level bridge
snapshot service used by SABR thin-client routes.
"""

from .bridge_client import (
    DEFAULT_BRIDGE_URL,
    OFFLINE_WORKER_MESSAGE,
    BridgeAPIError,
    BridgeOfflineError,
    bridge_endpoint,
    bridge_url,
    format_bridge_error,
    request_json,
    request_json_sync,
)
from .bridge_service import (
    AiiDABridgeService,
    BridgeConnectionState,
    BridgeResourceCounts,
    BridgeSnapshot,
    bridge_service,
)

__all__ = [
    "DEFAULT_BRIDGE_URL",
    "OFFLINE_WORKER_MESSAGE",
    "BridgeAPIError",
    "BridgeOfflineError",
    "bridge_endpoint",
    "bridge_url",
    "format_bridge_error",
    "request_json",
    "request_json_sync",
    "AiiDABridgeService",
    "BridgeConnectionState",
    "BridgeResourceCounts",
    "BridgeSnapshot",
    "bridge_service",
]
