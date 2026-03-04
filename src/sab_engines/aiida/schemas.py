from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class FrontendChatRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=12000)
    model_name: str | None = None
    context_archive: str | None = None
    context_node_ids: list[int] | None = None
    context_pks: list[int] | None = None
    metadata: dict[str, Any] | None = None


class FrontendStopChatRequest(BaseModel):
    turn_id: int | None = None


class SubmissionDraftRequest(BaseModel):
    draft: dict[str, Any] | list[dict[str, Any]] = Field(default_factory=dict)


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


class FrontendGroupCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class FrontendGroupRenameRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)


class FrontendGroupAssignNodesRequest(BaseModel):
    node_pks: list[int] = Field(default_factory=list)


class FrontendNodeSoftDeleteRequest(BaseModel):
    deleted: bool = True


class NodeHoverMetadataResponse(BaseModel):
    pk: int
    formula: str | None = None
    spacegroup: str | None = None
    node_type: str = "Unknown"


class InfrastructureComputerCode(BaseModel):
    pk: int
    label: str
    description: str | None = None
    default_calc_job_plugin: str | None = None


class InfrastructureComputer(BaseModel):
    pk: int
    label: str
    hostname: str
    description: str | None = None
    scheduler_type: str
    transport_type: str
    is_enabled: bool
    codes: list[InfrastructureComputerCode] = Field(default_factory=list)


class ParseInfrastructureRequest(BaseModel):
    text: str = Field(..., min_length=1)
    ssh_host_details: dict[str, Any] | None = None
