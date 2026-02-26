from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.sab_core.services.bridge_service import bridge_service

router = APIRouter(prefix="/api/aiida", tags=["aiida-bridge"])


class BridgeStatusResponse(BaseModel):
    status: Literal["online", "offline"]
    url: str
    environment: str


class SystemCountsResponse(BaseModel):
    computers: int = 0
    codes: int = 0
    workchains: int = 0


class BridgeSystemInfoResponse(BaseModel):
    profile: str = "unknown"
    counts: SystemCountsResponse = Field(default_factory=SystemCountsResponse)
    daemon_status: bool = False


class ComputerResourceResponse(BaseModel):
    label: str
    hostname: str
    description: str | None = None


class CodeResourceResponse(BaseModel):
    label: str
    default_plugin: str | None = None
    computer_label: str | None = None


class BridgeResourcesResponse(BaseModel):
    computers: list[ComputerResourceResponse] = Field(default_factory=list)
    codes: list[CodeResourceResponse] = Field(default_factory=list)


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


@router.get("/system", response_model=BridgeSystemInfoResponse)
async def get_bridge_system_info() -> BridgeSystemInfoResponse:
    try:
        payload = await bridge_service.get_system_info()
        return BridgeSystemInfoResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/system failed -> {error_message}")
        return BridgeSystemInfoResponse()


@router.get("/resources", response_model=BridgeResourcesResponse)
async def get_bridge_resources() -> BridgeResourcesResponse:
    try:
        payload = await bridge_service.get_resources()
        return BridgeResourcesResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/resources failed -> {error_message}")
        return BridgeResourcesResponse()
