from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from src.sab_core.services.bridge_service import bridge_service

router = APIRouter(prefix="/api/aiida", tags=["aiida-bridge"])


class BridgeStatusResponse(BaseModel):
    status: Literal["online", "offline"]
    url: str
    environment: str


@router.get("/status", response_model=BridgeStatusResponse)
async def get_bridge_status() -> BridgeStatusResponse:
    try:
        snapshot = await bridge_service.get_status()
        return BridgeStatusResponse(
            status=snapshot.status,
            url=snapshot.url,
            environment=snapshot.environment,
        )
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/status failed -> {error_message}")
        return BridgeStatusResponse(
            status="offline",
            url=bridge_service.bridge_url,
            environment="Local Sandbox",
        )


@router.get("/plugins", response_model=list[str])
async def get_bridge_plugins() -> list[str]:
    try:
        return await bridge_service.get_plugins()
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/plugins failed -> {error_message}")
        return []
