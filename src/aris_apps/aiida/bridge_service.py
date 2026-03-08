"""Backward-compatible bridge service exports.

The worker service implementation now lives in `client.py` as
`AiiDAWorkerClient`. This module keeps historical imports stable.
"""

from __future__ import annotations

from .client import (
    AiiDABridgeService,
    BridgeConnectionState,
    BridgeResourceCounts,
    BridgeSnapshot,
    bridge_service,
)

__all__ = [
    "AiiDABridgeService",
    "BridgeConnectionState",
    "BridgeResourceCounts",
    "BridgeSnapshot",
    "bridge_service",
]
