"""Tests for chat context metadata normalization and priority injection."""

from types import SimpleNamespace

from src.sab_engines.aiida.chat import service as chat_service


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
        "Request failed: status_code: 503, model_name: gemini-3-pro-preview, "
        "body: {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. "
        "Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
    )
    assert chat_service._is_retryable_model_unavailable_error(error) is True


def test_is_retryable_model_unavailable_error_ignores_non_retryable_errors() -> None:
    model_rejected = RuntimeError("Request failed: status_code: 404, model is not found for api version")
    assert chat_service._is_retryable_model_unavailable_error(model_rejected) is False
