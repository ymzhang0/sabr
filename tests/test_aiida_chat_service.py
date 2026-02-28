"""Tests for chat context metadata normalization and priority injection."""

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
