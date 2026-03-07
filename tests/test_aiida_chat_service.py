"""Tests for chat context metadata normalization and priority injection."""

from pathlib import Path
from types import SimpleNamespace

from src.sab_engines.aiida.chat import service as chat_service


class _Memory:
    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def get_kv(self, key: str):
        return self._values.get(key)

    def set_kv(self, key: str, value: object) -> None:
        self._values[key] = value


def _make_chat_state() -> SimpleNamespace:
    return SimpleNamespace(memory=_Memory(), chat_version=0)


def test_merge_context_node_ids_prefers_union_of_fields() -> None:
    metadata = {
        "context_pks": [4, "8", 4],
        "context_node_pks": ["8", 10, "invalid"],
    }

    merged = chat_service._merge_context_node_ids([2, 4], metadata)

    assert merged == [2, 4, 8, 10]


def test_inject_context_priority_instruction_adds_primary_scope() -> None:
    intent = "Compare these nodes and summarize."

    scoped = chat_service._inject_context_priority_instruction(intent, [22, 35])

    assert "context_pks: [22, 35]" in scoped
    assert "Treat these PKs as the primary subjects" in scoped
    assert "USER REQUEST" in scoped
    assert intent in scoped


def test_serialize_chat_history_keeps_payload() -> None:
    history = [
        {
            "role": "assistant",
            "text": "Validation ready",
            "status": "done",
            "turn_id": 3,
            "payload": {
                "type": "SUBMISSION_DRAFT",
                "submission_draft": {
                    "process_label": "PwBaseWorkChain",
                    "inputs": {},
                    "primary_inputs": {"structure": {"label": "Structure", "value": "PK 11", "pk": 11}},
                    "advanced_settings": {"num_machines": 2},
                    "meta": {"pk_map": [{"pk": 11}]},
                },
            },
        }
    ]

    serialized = chat_service.serialize_chat_history(history)

    assert serialized[0]["payload"]["type"] == "SUBMISSION_DRAFT"
    assert serialized[0]["payload"]["submission_draft"]["meta"]["pk_map"][0]["pk"] == 11


def test_build_chat_message_payload_includes_submission_draft_fields() -> None:
    pending = {
        "draft": {
            "builder": {
                "structure_pk": 11,
                "metadata": {
                    "options": {
                        "resources": {"num_machines": 2, "num_mpiprocs_per_machine": 8},
                    },
                    "computer": "localhost",
                },
            }
        },
        "validation_summary": {"status": "VALIDATION_OK", "is_valid": True},
    }
    output = SimpleNamespace(data_payload={"source": "agent"})
    deps = SimpleNamespace(get_registry_value=lambda key: pending if key == "aiida_pending_submission" else None)

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=["GET management.statistics", "POST submission.draft-builder"],
    )

    assert payload is not None
    assert payload["type"] == "SUBMISSION_DRAFT"
    assert payload["tool_calls"] == ["GET management.statistics", "POST submission.draft-builder"]
    submission_draft = payload["submission_draft"]
    assert submission_draft["inputs"]["structure_pk"] == 11
    assert submission_draft["primary_inputs"]["structure"]["pk"] == 11
    assert submission_draft["advanced_settings"]["num_machines"] == 2
    assert submission_draft["advanced_settings"]["num_mpiprocs_per_machine"] == 8
    assert submission_draft["meta"]["pk_map"][0]["pk"] == 11
    assert submission_draft["meta"]["target_computer"] == "localhost"
    assert submission_draft["meta"]["parallel_settings"]["num_machines"] == 2
    assert submission_draft["meta"]["validation_summary"]["status"] == "VALIDATION_OK"


def test_build_chat_message_payload_reads_pending_submission_from_memory() -> None:
    pending = {
        "draft": {
            "builder": {
                "structure_pk": 19,
                "metadata": {"options": {"resources": {"num_machines": 1}}},
            }
        },
        "validation_summary": {"status": "VALIDATION_OK", "is_valid": True},
    }

    class _Memory:
        def get_kv(self, key: str):
            if key == "aiida_pending_submission":
                return pending
            return None

    deps = SimpleNamespace(
        get_registry_value=lambda _key: None,
        memory=_Memory(),
    )
    output = SimpleNamespace(data_payload={"source": "agent"})

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=None,
    )

    assert payload is not None
    assert payload["type"] == "SUBMISSION_DRAFT"
    assert payload["submission_draft"]["inputs"]["structure_pk"] == 19
    assert payload["submission_draft"]["meta"]["validation_summary"]["status"] == "VALIDATION_OK"


def test_build_chat_message_payload_extracts_submission_draft_from_answer_text() -> None:
    output = SimpleNamespace(data_payload={"source": "agent"})
    deps = SimpleNamespace(get_registry_value=lambda _key: None)
    answer_text = (
        "Validation complete.\n\n"
        "[SUBMISSION_DRAFT]\n"
        "{\n"
        '  "process_label": "PwBaseWorkChain",\n'
        '  "inputs": {"structure_pk": 21},\n'
        '  "meta": {"pk_map": [{"pk": 21}]}\n'
        "}"
    )

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=None,
        answer_text=answer_text,
    )

    assert payload is not None
    assert payload["type"] == "SUBMISSION_DRAFT"
    assert payload["submission_draft"]["process_label"] == "PwBaseWorkChain"
    assert payload["submission_draft"]["meta"]["pk_map"][0]["pk"] == 21


def test_build_chat_message_payload_extracts_submission_draft_from_output_payload() -> None:
    output = SimpleNamespace(
        data_payload={
            "type": "SUBMISSION_DRAFT",
            "submission_draft": {
                "process_label": "PwRelaxWorkChain",
                "inputs": {"structure_pk": 34},
                "meta": {"pk_map": [{"pk": 34}]},
            },
        }
    )
    deps = SimpleNamespace(get_registry_value=lambda _key: None)

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=None,
        answer_text="",
    )

    assert payload is not None
    assert payload["type"] == "SUBMISSION_DRAFT"
    assert payload["submission_draft"]["process_label"] == "PwRelaxWorkChain"
    assert payload["submission_draft"]["meta"]["pk_map"][0]["pk"] == 34


def test_build_chat_message_payload_extracts_submission_draft_from_output_draft_shape() -> None:
    output = SimpleNamespace(
        data_payload={
            "status": "SUBMISSION_DRAFT",
            "draft": {
                "builder": {
                    "structure_pk": 56,
                    "metadata": {
                        "options": {
                            "resources": {"num_machines": 2},
                        }
                    },
                }
            },
            "validation_summary": {"status": "VALIDATION_OK", "is_valid": True},
        }
    )
    deps = SimpleNamespace(get_registry_value=lambda _key: None)

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=None,
        answer_text="",
    )

    assert payload is not None
    assert payload["type"] == "SUBMISSION_DRAFT"
    assert payload["submission_draft"]["inputs"]["structure_pk"] == 56
    assert payload["submission_draft"]["meta"]["validation_summary"]["status"] == "VALIDATION_OK"


def test_build_chat_message_payload_surfaces_recovery_plan_and_next_step() -> None:
    output = SimpleNamespace(
        data_payload={
            "status": "SUBMISSION_BLOCKED",
            "next_step": "Inspect the spec, verify resources, and ask the user before retrying.",
            "recovery_plan": {
                "status": "blocked",
                "summary": "Missing required inputs: structure, code",
                "missing_ports": ["structure", "code"],
                "issues": [
                    {
                        "type": "missing_required_inputs",
                        "message": "Required inputs are still missing after builder construction: structure, code",
                    }
                ],
                "recommended_actions": [
                    {
                        "action": "inspect_spec",
                        "reason": "Review the WorkChain spec first.",
                    }
                ],
            },
        }
    )
    deps = SimpleNamespace(get_registry_value=lambda _key: None)

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=["POST submission.draft-builder"],
        answer_text="",
    )

    assert payload is not None
    assert payload["status"] == "SUBMISSION_BLOCKED"
    assert payload["next_step"] == "Inspect the spec, verify resources, and ask the user before retrying."
    assert payload["recovery_plan"]["summary"] == "Missing required inputs: structure, code"
    assert payload["recovery_plan"]["missing_ports"] == ["structure", "code"]
    assert payload["tool_calls"] == ["POST submission.draft-builder"]


def test_build_chat_message_payload_extracts_submission_draft_from_submission_tag_field() -> None:
    output = SimpleNamespace(
        data_payload={
            "submission_draft_tag": (
                "[SUBMISSION_DRAFT]\n"
                "{\n"
                '  "process_label": "PwBaseWorkChain",\n'
                '  "inputs": {"structure_pk": 77},\n'
                '  "meta": {"pk_map": [{"pk": 77}]}\n'
                "}"
            )
        }
    )
    deps = SimpleNamespace(get_registry_value=lambda _key: None)

    payload = chat_service._build_chat_message_payload(
        output,
        deps,
        tool_calls=None,
        answer_text="",
    )

    assert payload is not None
    assert payload["type"] == "SUBMISSION_DRAFT"
    assert payload["submission_draft"]["process_label"] == "PwBaseWorkChain"
    assert payload["submission_draft"]["meta"]["pk_map"][0]["pk"] == 77


def test_build_user_message_payload_keeps_context_nodes() -> None:
    metadata = {
        "context_nodes": [
            {"pk": 8, "label": "Si", "formula": "Si2", "node_type": "StructureData"},
            {"pk": "12", "label": "", "node_type": "WorkChainNode"},
            {"pk": "bad", "label": "Skip me"},
        ]
    }

    payload = chat_service._build_user_message_payload(metadata, [8, 12, 8])

    assert payload == {
        "context_pks": [8, 12],
        "context_nodes": [
            {"pk": 8, "label": "Si", "formula": "Si2", "node_type": "StructureData"},
            {"pk": 12, "label": "#12", "formula": None, "node_type": "WorkChainNode"},
        ],
    }


def test_build_user_message_payload_keeps_session_preferences() -> None:
    metadata = {
        "context_nodes": [
            {"pk": 8, "label": "Si", "formula": "Si2", "node_type": "StructureData"},
        ],
        "pinned_nodes": [
            {"pk": 21, "label": "Pinned Si", "formula": "Si2", "node_type": "StructureData"},
        ],
        "session_environment": "quantumespresso",
        "prompt_override": "Keep four decimal places.",
        "session_parameters": [
            {"key": "ecutwfc", "value": "40 Ry"},
            {"key": "kspacing", "value": "0.15 1/Ang"},
        ],
    }

    payload = chat_service._build_user_message_payload(metadata, [8, 21])

    assert payload is not None
    assert payload["session_environment"] == "quantumespresso"
    assert payload["prompt_override"] == "Keep four decimal places."
    assert payload["pinned_nodes"][0]["pk"] == 21
    assert payload["session_parameters"][0]["key"] == "ecutwfc"


def test_inject_session_preference_instruction_adds_session_defaults() -> None:
    intent = "Run a relaxation."
    metadata = {
        "session_environment": "quantumespresso",
        "prompt_override": "Keep four decimal places.",
        "pinned_nodes": [{"pk": 22, "label": "Si", "node_type": "StructureData"}],
        "session_parameters": [{"key": "ecutwfc", "value": "40 Ry"}],
    }

    scoped = chat_service._inject_session_preference_instruction(intent, metadata)

    assert "SESSION PREFERENCES" in scoped
    assert "active_environment: quantumespresso" in scoped
    assert "pinned_nodes: [#22]" in scoped
    assert "session_parameters: ecutwfc=40 Ry" in scoped
    assert "prompt_override: Keep four decimal places." in scoped
    assert intent in scoped


def test_build_submission_draft_text_block_for_ui_tag() -> None:
    payload = {
        "type": "SUBMISSION_DRAFT",
        "submission_draft": {
            "process_label": "PwBaseWorkChain",
            "inputs": {"structure_pk": 11},
            "primary_inputs": {"structure": {"label": "Structure", "value": "PK 11", "pk": 11}},
            "advanced_settings": {},
            "meta": {"pk_map": [{"pk": 11}]},
        },
    }

    block = chat_service._build_submission_draft_text_block(payload)

    assert block is not None
    assert block.startswith("[SUBMISSION_DRAFT]\n{")
    assert '"process_label": "PwBaseWorkChain"' in block
    assert '"structure_pk": 11' in block


def test_normalize_submission_draft_payload_derives_primary_and_advanced() -> None:
    draft = {
        "builder": {
            "structure_pk": 22,
            "metadata": {
                "options": {
                    "resources": {
                        "num_machines": 1,
                        "num_mpiprocs_per_machine": 4,
                    }
                }
            },
            "parameters": {
                "SYSTEM": {
                    "ecutwfc": 80,
                }
            },
        }
    }

    normalized = chat_service._normalize_submission_draft_payload(
        {},
        draft=draft,
        validation=None,
        validation_summary=None,
    )

    assert normalized["primary_inputs"]["structure"]["pk"] == 22
    assert normalized["advanced_settings"]["num_mpiprocs_per_machine"] == 4
    assert normalized["advanced_settings"]["ecutwfc"] == 80
    assert "num_machines" not in normalized["advanced_settings"]
    assert isinstance(normalized["all_inputs"], dict)
    assert isinstance(normalized["input_groups"], list)
    assert normalized["meta"]["input_groups"] == normalized["input_groups"]


def test_extract_submission_inputs_ignores_request_wrapper_only_payload() -> None:
    draft = {
        "workchain": "quantumespresso.pw.relax",
        "structure_pk": 264,
        "code": "pw-7.5@localhost",
        "protocol": "moderate",
        "overrides": {},
    }

    extracted = chat_service._extract_submission_inputs(draft)

    assert extracted == {}


def test_extract_submission_inputs_prefers_nested_inputs_namespace() -> None:
    draft = {
        "builder": {
            "inputs": {
                "base": {
                    "pw": {
                        "code": "pw-7.5@localhost",
                    }
                },
                "structure": 264,
            },
            "code": "pw-7.5@localhost",
            "protocol": "moderate",
        }
    }

    extracted = chat_service._extract_submission_inputs(draft)

    assert "base" in extracted
    assert "code" not in extracted


def test_normalize_submission_draft_payload_builds_port_grouping_with_ui_types() -> None:
    normalized = chat_service._normalize_submission_draft_payload(
        {
            "process_label": "PwRelaxWorkChain",
            "inputs": {
                "base": {
                    "pw": {
                        "parameters": {
                            "SYSTEM": {"ecutwfc": 55},
                        }
                    }
                },
                "kpoints": {"mesh": [4, 4, 1]},
                "metadata": {
                    "options": {
                        "resources": {"num_machines": 2},
                        "max_wallclock_seconds": 3600,
                    }
                },
                "protocol": "moderate",
                "pseudo_family": "PseudoDojo/0.5/PBE/SR/standard/upf",
            },
            "advanced_settings": {"protocol": "moderate"},
        },
        draft=None,
        validation=None,
        validation_summary=None,
    )

    groups = normalized["input_groups"]
    assert isinstance(groups, list)
    group_titles = {entry.get("title") for entry in groups}
    assert "Computational Details" in group_titles
    assert "Brillouin Zone" in group_titles
    assert "System Environment" in group_titles
    assert "Physics Protocol" in group_titles

    mesh_entry = normalized["all_inputs"]["kpoints.mesh"]
    assert mesh_entry["ui_type"] == "mesh"


def test_update_assistant_message_keeps_existing_text_when_status_payload_arrives() -> None:
    state = SimpleNamespace(
        chat_history=[
            {
                "role": "assistant",
                "turn_id": 9,
                "text": "Partial result is already visible.",
                "status": "thinking",
            }
        ],
        chat_version=0,
    )

    chat_service._update_assistant_message(
        state,
        9,
        "Running: custom script...",
        status="thinking",
        payload={
            "type": "status",
            "tool_calls": ["POST management.run-python"],
            "status": {
                "current_step": "Running custom script",
                "steps": ["Running custom script"],
            },
        },
    )

    message = state.chat_history[0]
    assert message["text"] == "Partial result is already visible."
    assert message["status"] == "thinking"
    assert message["payload"]["type"] == "status"
    assert message["payload"]["status"]["current_step"] == "Running custom script"


def test_is_retryable_model_unavailable_error_detects_high_demand_503() -> None:
    error = RuntimeError(
        "Request failed: status_code: 503, model_name: gemini-3-flash-preview, "
        "body: {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. "
        "Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
    )
    assert chat_service._is_retryable_model_unavailable_error(error) is True


def test_is_retryable_model_unavailable_error_ignores_non_retryable_errors() -> None:
    model_rejected = RuntimeError("Request failed: status_code: 404, model is not found for api version")
    assert chat_service._is_retryable_model_unavailable_error(model_rejected) is False


def test_create_chat_session_archives_previous_active_session() -> None:
    state = _make_chat_state()

    original = chat_service.create_chat_session(state, title="Original", activate=True)
    fresh = chat_service.create_chat_session(
        state,
        title="Fresh",
        activate=True,
        archive_session_id=original["id"],
    )

    sessions = {session["id"]: session for session in chat_service.list_chat_sessions(state)}

    assert chat_service.get_active_chat_session_id(state) == fresh["id"]
    assert sessions[original["id"]]["is_archived"] is True
    assert sessions[fresh["id"]]["is_archived"] is False


def test_activate_chat_session_unarchives_history_session() -> None:
    state = _make_chat_state()

    archived = chat_service.create_chat_session(state, title="Archived candidate", activate=True)
    current = chat_service.create_chat_session(
        state,
        title="Current",
        activate=True,
        archive_session_id=archived["id"],
    )

    restored = chat_service.activate_chat_session(state, archived["id"])

    assert current["id"] != archived["id"]
    assert restored is not None
    assert restored["id"] == archived["id"]
    assert restored["is_archived"] is False
    assert chat_service.get_active_chat_session_id(state) == archived["id"]


def test_normalize_chat_session_store_skips_archived_active_session() -> None:
    normalized = chat_service._normalize_chat_session_store(
        {
            "active_session_id": "archived-session",
            "sessions": [
                {"id": "archived-session", "title": "Archived", "is_archived": True},
                {"id": "active-session", "title": "Active", "is_archived": False},
            ],
        }
    )

    assert normalized["active_session_id"] == "active-session"


def test_create_chat_session_creates_default_project_workspace(tmp_path) -> None:
    state = _make_chat_state()
    original_root = chat_service.settings.SABR_PROJECTS_ROOT
    chat_service.settings.SABR_PROJECTS_ROOT = str(tmp_path)
    try:
        session = chat_service.create_chat_session(state, title="Workspace session", activate=True)
    finally:
        chat_service.settings.SABR_PROJECTS_ROOT = original_root

    assert session["project_id"]
    assert session["project_label"] == "Default Project"
    workspace_path = Path(session["workspace_path"])
    assert workspace_path.exists()
    assert workspace_path.name == session["id"]
    assert workspace_path.parent.name == "sessions"


def test_create_chat_project_assigns_new_sessions_to_requested_project(tmp_path) -> None:
    state = _make_chat_state()
    original_root = chat_service.settings.SABR_PROJECTS_ROOT
    chat_service.settings.SABR_PROJECTS_ROOT = str(tmp_path)
    try:
        project = chat_service.create_chat_project(
            state,
            name="Born Charge Study",
            root_path=str(tmp_path / "born-study"),
            activate=True,
        )
        session = chat_service.create_chat_session(
            state,
            title="Analyze Born charges",
            activate=True,
            project_id=project["id"],
        )
    finally:
        chat_service.settings.SABR_PROJECTS_ROOT = original_root

    assert session["project_id"] == project["id"]
    assert session["project_label"] == "Born Charge Study"
    assert Path(session["workspace_path"]).parent.parent == Path(project["root_path"])


def test_list_chat_session_workspace_files_returns_saved_entries(tmp_path) -> None:
    state = _make_chat_state()
    original_root = chat_service.settings.SABR_PROJECTS_ROOT
    chat_service.settings.SABR_PROJECTS_ROOT = str(tmp_path)
    try:
        session = chat_service.create_chat_session(state, title="Workspace browser", activate=True)
        workspace_path = Path(session["workspace_path"])
        (workspace_path / "plots").mkdir(parents=True, exist_ok=True)
        (workspace_path / "plots" / "band-structure.png").write_bytes(b"png")
        payload = chat_service.list_chat_session_workspace_files(state, session["id"], relative_path="plots")
    finally:
        chat_service.settings.SABR_PROJECTS_ROOT = original_root

    assert payload is not None
    assert payload["relative_path"] == "plots"
    assert payload["entries"][0]["name"] == "band-structure.png"
