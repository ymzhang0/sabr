from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.sab_core.engines.aiida.bridge_service import bridge_service

router = APIRouter(prefix="/api/aiida", tags=["aiida-bridge"])


class SystemCountsResponse(BaseModel):
    computers: int = 0
    codes: int = 0
    workchains: int = 0


class BridgeStatusResponse(BaseModel):
    status: Literal["online", "offline"]
    url: str
    environment: str
    profile: str = "unknown"
    daemon_status: bool = False
    resources: SystemCountsResponse = Field(default_factory=SystemCountsResponse)
    plugins: list[str] = Field(default_factory=list)


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


class BridgeProfileResponse(BaseModel):
    name: str
    is_default: bool = False
    is_active: bool = False


class BridgeProfilesResponse(BaseModel):
    current_profile: str | None = None
    default_profile: str | None = None
    profiles: list[BridgeProfileResponse] = Field(default_factory=list)


class BridgeSwitchProfileRequest(BaseModel):
    profile: str = Field(..., min_length=1)


class BridgeSwitchProfileResponse(BaseModel):
    status: str = "switched"
    current_profile: str | None = None


@router.get("/status", response_model=BridgeStatusResponse)
async def get_bridge_status() -> BridgeStatusResponse:
    try:
        snapshot = await bridge_service.get_status()
        return BridgeStatusResponse(
            status=snapshot.status,
            url=snapshot.url,
            environment=snapshot.environment,
            profile=snapshot.profile,
            daemon_status=snapshot.daemon_status,
            resources=SystemCountsResponse(
                computers=snapshot.resources.computers,
                codes=snapshot.resources.codes,
                workchains=snapshot.resources.workchains,
            ),
            plugins=list(snapshot.plugins),
        )
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/status failed -> {error_message}")
        return BridgeStatusResponse(
            status="offline",
            url=bridge_service.bridge_url,
            environment="Remote Bridge",
            profile="unknown",
            daemon_status=False,
            resources=SystemCountsResponse(),
            plugins=[],
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
        snapshot = await bridge_service.get_status()
        return BridgeSystemInfoResponse(
            profile=snapshot.profile,
            counts=SystemCountsResponse(
                computers=snapshot.resources.computers,
                codes=snapshot.resources.codes,
                workchains=snapshot.resources.workchains,
            ),
            daemon_status=snapshot.daemon_status,
        )
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


@router.get("/profiles", response_model=BridgeProfilesResponse)
async def get_bridge_profiles() -> BridgeProfilesResponse:
    try:
        payload = await bridge_service.get_profiles()
        return BridgeProfilesResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/profiles failed -> {error_message}")
        return BridgeProfilesResponse()


@router.post("/profiles/switch", response_model=BridgeSwitchProfileResponse)
async def switch_bridge_profile(payload: BridgeSwitchProfileRequest) -> BridgeSwitchProfileResponse:
    try:
        raw = await bridge_service.switch_profile(payload.profile)
        return BridgeSwitchProfileResponse.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        error_message = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: /api/aiida/profiles/switch failed -> {error_message}")
        return BridgeSwitchProfileResponse(status="error", current_profile=None)
