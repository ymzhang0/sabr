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


class FrontendChatSessionCreateRequest(BaseModel):
    title: str | None = None
    snapshot: dict[str, Any] | None = None
    archive_session_id: str | None = None
    project_id: str | None = None


class FrontendChatSessionUpdateRequest(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    snapshot: dict[str, Any] | None = None


class FrontendChatSessionTitleUpdateRequest(BaseModel):
    title: str | None = None


class FrontendChatProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    root_path: str | None = None


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


class NodeScriptResponse(BaseModel):
    pk: int
    node_type: str
    language: str = "python"
    script: str


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


class InfrastructureExportResponse(BaseModel):
    kind: str
    label: str
    filename: str
    format: str = "yaml"
    content: str


class ParseInfrastructureRequest(BaseModel):
    text: str = Field(..., min_length=1)
    ssh_host_details: dict[str, Any] | None = None
class UserInfoResponse(BaseModel):
    first_name: str
    last_name: str
    email: str
    institution: str


class ProfileSetupRequest(BaseModel):
    profile_name: str
    first_name: str
    last_name: str
    email: str
    institution: str
    filepath: str
    backend: str = "core.sqlite_dos"
    set_as_default: bool = True

class CodeSetupRequest(BaseModel):
    computer_label: str
    label: str
    description: str | None = None
    default_calc_job_plugin: str
    remote_abspath: str
    prepend_text: str | None = None
    append_text: str | None = None
    with_mpi: bool = True
    use_double_quotes: bool = False

class CodeDetailedResponse(BaseModel):
    pk: int
    label: str
    description: str | None = None
    default_calc_job_plugin: str
    remote_abspath: str
    prepend_text: str | None = None
    append_text: str | None = None
    with_mpi: bool
    use_double_quotes: bool
