from __future__ import annotations

import asyncio
import hashlib
import json
import time
from contextlib import suppress
from typing import Any, Callable

from loguru import logger
from pydantic_ai.settings import ModelSettings

from src.sab_engines.aiida.client import reset_bridge_call_listener, set_bridge_call_listener
from src.sab_engines.aiida.presenters.workflow_view import enrich_submission_draft_payload
from src.sab_core.config import settings
from src.sab_core.logging_utils import log_event

_PENDING_SUBMISSION_KEY = "aiida_pending_submission"
_SUBMISSION_DRAFT_PREFIX = "[SUBMISSION_DRAFT]"
_KNOWN_PARALLEL_KEYS = {
    "num_machines",
    "num_mpiprocs_per_machine",
    "tot_num_mpiprocs",
    "num_cores_per_machine",
    "num_cores_per_mpiproc",
    "max_wallclock_seconds",
    "queue_name",
    "withmpi",
    "account",
    "qos",
    "npool",
    "nk",
    "ntg",
    "ndiag",
}
_CRITICAL_ADVANCED_KEYS = {
    "kpoints_distance",
    "kpoints_mesh",
    "kpoints",
    "mesh",
    "ecutwfc",
    "ecutrho",
    "occupations",
    "smearing",
    "degauss",
    "conv_thr",
    "mixing_beta",
    "diagonalization",
    "electron_maxstep",
    "nstep",
    "hubbard_u",
    "hubbard_v",
    "spin_type",
    "tot_charge",
    "tot_magnetization",
    "press_conv_thr",
    "forc_conv_thr",
    *_KNOWN_PARALLEL_KEYS,
}


def _draft_fragment_hash(fragment: str) -> str:
    return hashlib.sha1(fragment.encode("utf-8", errors="replace")).hexdigest()[:12]


def normalize_context_node_ids(raw: Any) -> list[int]:
    if raw is None:
        return []

    values: list[Any]
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return []
        values = [part.strip() for part in stripped.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        values = [raw]

    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        try:
            pk = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if pk <= 0 or pk in seen:
            continue
        seen.add(pk)
        deduped.append(pk)
        if len(deduped) >= 30:
            break
    return deduped


def serialize_chat_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in history:
        item = {
            "role": str(message.get("role", "assistant")),
            "text": str(message.get("text", "")),
            "status": str(message.get("status", "done")),
            "turn_id": int(message.get("turn_id") or 0),
        }
        message_payload = message.get("payload")
        if isinstance(message_payload, dict):
            item["payload"] = message_payload
        payload.append(item)
    return payload


def get_chat_history(state: Any) -> list[dict[str, Any]]:
    history = getattr(state, "chat_history", None)
    if history is None:
        history = []
        state.chat_history = history
    if not hasattr(state, "chat_version"):
        state.chat_version = 0
    return history


def touch_chat(state: Any) -> None:
    state.chat_version = getattr(state, "chat_version", 0) + 1


def _ensure_chat_lock(state: Any) -> asyncio.Lock:
    lock = getattr(state, "chat_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        state.chat_lock = lock
    return lock


def _ensure_chat_task_registry(state: Any) -> dict[int, asyncio.Task]:
    tasks = getattr(state, "chat_turn_tasks", None)
    if tasks is None:
        tasks = {}
        state.chat_turn_tasks = tasks
    return tasks


def _is_status_only_text(text: str) -> bool:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return False
    return all(
        line.lower().startswith("thinking:")
        or line.lower().startswith("running:")
        or line.lower().startswith("step:")
        or line.lower().startswith("⚙️ [step]")
        for line in lines
    )


def _merge_message_payload(
    existing_payload: dict[str, Any] | None,
    incoming_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(existing_payload, dict):
        return incoming_payload
    if not isinstance(incoming_payload, dict):
        return existing_payload

    merged = dict(existing_payload)
    for key, value in incoming_payload.items():
        if key == "tool_calls" and isinstance(merged.get("tool_calls"), list) and isinstance(value, list):
            deduped: list[str] = []
            seen: set[str] = set()
            for entry in [*merged["tool_calls"], *value]:
                cleaned = str(entry).strip()
                if not cleaned or cleaned in seen:
                    continue
                seen.add(cleaned)
                deduped.append(cleaned)
            merged["tool_calls"] = deduped
            continue
        if (
            key == "status"
            and isinstance(merged.get("status"), dict)
            and isinstance(value, dict)
        ):
            merged_status = dict(merged["status"])
            for status_key, status_value in value.items():
                if (
                    status_key == "steps"
                    and isinstance(merged_status.get("steps"), list)
                    and isinstance(status_value, list)
                ):
                    deduped_steps: list[str] = []
                    seen_steps: set[str] = set()
                    for step in [*merged_status["steps"], *status_value]:
                        step_text = str(step).strip()
                        if not step_text or step_text in seen_steps:
                            continue
                        seen_steps.add(step_text)
                        deduped_steps.append(step_text)
                    merged_status["steps"] = deduped_steps
                else:
                    merged_status[status_key] = status_value
            merged["status"] = merged_status
            continue
        merged[key] = value
    return merged


def _update_assistant_message(
    state: Any,
    turn_id: int,
    text: str | None,
    status: str = "thinking",
    *,
    payload: dict[str, Any] | None = None,
) -> None:
    chat_history = get_chat_history(state)
    for msg in reversed(chat_history):
        if msg.get("role") == "assistant" and msg.get("turn_id") == turn_id:
            previous_text = str(msg.get("text") or "")
            if text is None:
                next_text = previous_text
            else:
                incoming_text = str(text)
                if incoming_text.strip() and previous_text.strip():
                    if _is_status_only_text(incoming_text) and not _is_status_only_text(previous_text):
                        next_text = previous_text
                    else:
                        next_text = incoming_text
                elif not incoming_text.strip() and previous_text.strip():
                    next_text = previous_text
                else:
                    next_text = incoming_text

            msg["text"] = next_text
            msg["status"] = status
            if isinstance(payload, dict):
                merged_payload = _merge_message_payload(
                    msg.get("payload") if isinstance(msg.get("payload"), dict) else None,
                    payload,
                )
                if isinstance(merged_payload, dict):
                    msg["payload"] = merged_payload
            touch_chat(state)
            return
    logger.warning(log_event("aiida.chat_turn.message_update_missed", turn_id=turn_id, status=status))


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            parsed = int(stripped)
            return parsed if parsed > 0 else None
    return None


def _normalize_focus_context_nodes(raw_nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        return []

    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for entry in raw_nodes:
        if not isinstance(entry, dict):
            continue
        pk = _coerce_positive_int(entry.get("pk"))
        if pk is None or pk in seen:
            continue
        seen.add(pk)

        label_raw = entry.get("label")
        label = str(label_raw).strip() if isinstance(label_raw, str) else ""
        node_type_raw = entry.get("node_type")
        node_type = str(node_type_raw).strip() if isinstance(node_type_raw, str) else ""
        formula_raw = entry.get("formula")
        formula = str(formula_raw).strip() if isinstance(formula_raw, str) else ""
        normalized.append(
            {
                "pk": pk,
                "label": label or f"#{pk}",
                "formula": formula or None,
                "node_type": node_type or "Unknown",
            }
        )
    return normalized


def _build_user_message_payload(
    metadata: dict[str, Any] | None,
    context_pks: list[int],
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    normalized_pks = normalize_context_node_ids(context_pks)
    if normalized_pks:
        payload["context_pks"] = normalized_pks

    context_nodes = _normalize_focus_context_nodes((metadata or {}).get("context_nodes"))
    if context_nodes:
        payload["context_nodes"] = context_nodes

    return payload or None


def _extract_submission_inputs(draft: dict[str, Any]) -> dict[str, Any]:
    for key in ("inputs", "builder", "draft"):
        value = draft.get(key)
        if isinstance(value, dict):
            return value
    return draft


def _find_first_named_value(payload: Any, candidate_keys: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).strip().lower()
            if lowered in candidate_keys and value not in (None, "", []):
                return value
            nested = _find_first_named_value(value, candidate_keys)
            if nested is not None:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _find_first_named_value(item, candidate_keys)
            if nested is not None:
                return nested
    return None


def _extract_target_computer(draft: dict[str, Any]) -> str | None:
    value = _find_first_named_value(
        draft,
        {"computer", "computer_label", "computer_name", "target_computer"},
    )
    if isinstance(value, dict):
        for key in ("label", "name", "computer_label", "computer_name"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
        pk = _coerce_positive_int(value.get("pk"))
        return f"PK #{pk}" if pk else None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _extract_process_label(draft: dict[str, Any]) -> str:
    value = _find_first_named_value(
        draft,
        {
            "process_label",
            "workchain",
            "workchain_label",
            "entry_point",
            "workflow",
            "workflow_label",
        },
    )
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return "AiiDA Workflow"


def _extract_parallel_settings(draft: dict[str, Any]) -> dict[str, Any]:
    settings: dict[str, Any] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).strip().lower()
                if lowered in _KNOWN_PARALLEL_KEYS and lowered not in settings:
                    settings[lowered] = value
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(draft)
    return settings


def _is_empty_submission_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _normalize_primary_input_field(label: str, value: Any) -> dict[str, Any] | None:
    if _is_empty_submission_value(value):
        return None

    field: dict[str, Any] = {"label": label}
    if isinstance(value, dict):
        pk = _coerce_positive_int(value.get("pk") or value.get("structure_pk") or value.get("code_pk"))
        display: str | None = None
        for key in ("label", "name", "value", "formula", "code_label", "family"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                display = candidate.strip()
                break
        if display is None and pk is not None:
            display = f"PK #{pk}"
        if display is None:
            display = json.dumps(value, ensure_ascii=True)
        field["value"] = display
        if pk is not None:
            field["pk"] = pk
        return field

    if isinstance(value, list):
        preview = ", ".join(str(item) for item in value[:4])
        suffix = " ..." if len(value) > 4 else ""
        field["value"] = preview + suffix
        return field

    scalar_pk = _coerce_positive_int(value)
    if scalar_pk is not None and label.lower() == "structure":
        field["value"] = f"PK #{scalar_pk}"
        field["pk"] = scalar_pk
        return field

    field["value"] = str(value)
    return field


def _extract_primary_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    primary_inputs: dict[str, Any] = {}

    code_value = _find_first_named_value(
        inputs,
        {"code", "code_label", "pw_code", "qe_code", "codes"},
    )
    code_field = _normalize_primary_input_field("Code", code_value)
    if isinstance(code_field, dict):
        primary_inputs["code"] = code_field

    structure_value = _find_first_named_value(
        inputs,
        {"structure", "structure_pk", "structure_id"},
    )
    structure_field = _normalize_primary_input_field("Structure", structure_value)
    if isinstance(structure_field, dict):
        primary_inputs["structure"] = structure_field

    pseudos_value = _find_first_named_value(
        inputs,
        {"pseudos", "pseudo", "pseudopotentials", "pseudo_family", "pseudo_family_label"},
    )
    pseudos_field = _normalize_primary_input_field("Pseudopotentials", pseudos_value)
    if isinstance(pseudos_field, dict):
        primary_inputs["pseudos"] = pseudos_field

    return primary_inputs


def _is_default_advanced_setting(key: str, value: Any) -> bool:
    lowered = key.strip().lower()
    if lowered in {
        "num_machines",
        "num_mpiprocs_per_machine",
        "tot_num_mpiprocs",
        "num_cores_per_machine",
        "num_cores_per_mpiproc",
        "npool",
        "nk",
        "ntg",
        "ndiag",
    }:
        parsed = _coerce_positive_int(value)
        return parsed == 1
    if lowered == "withmpi":
        return value is True
    if lowered == "protocol":
        return str(value).strip().lower() in {"default", "moderate"}
    return False


def _collect_advanced_settings(payload: Any) -> dict[str, Any]:
    settings: dict[str, Any] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lowered = str(key).strip().lower()
                if (
                    lowered in _CRITICAL_ADVANCED_KEYS
                    and lowered not in settings
                    and not _is_empty_submission_value(value)
                    and not _is_default_advanced_setting(lowered, value)
                ):
                    settings[lowered] = value
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return settings


def _normalize_recommended_inputs(
    raw_recommended: Any,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    source = raw_recommended if isinstance(raw_recommended, dict) else fallback
    normalized: dict[str, Any] = {}
    for key, value in source.items():
        normalized_key = str(key).strip().lower()
        if not normalized_key:
            continue
        if _is_empty_submission_value(value) or _is_default_advanced_setting(normalized_key, value):
            continue
        normalized[normalized_key] = value
    return normalized


def _collect_pk_map(payload: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    explicit_pk_list_keys = {"input_pks", "node_pks", "structure_pks"}

    def append_entry(pk: int, path: str, label: str) -> None:
        dedupe_key = (pk, path)
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        entries.append({"pk": pk, "path": path, "label": label})

    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_text = str(key)
                lowered = key_text.strip().lower()
                key_path = f"{path}.{key_text}" if path else key_text
                if lowered == "pk" or lowered.endswith("_pk"):
                    candidate = _coerce_positive_int(value)
                    if candidate is not None:
                        append_entry(candidate, key_path, key_text)
                elif lowered in explicit_pk_list_keys and isinstance(value, list):
                    for index, item in enumerate(value):
                        candidate = _coerce_positive_int(item)
                        if candidate is None:
                            continue
                        append_entry(candidate, f"{key_path}[{index}]", key_text)

                if isinstance(value, (dict, list)):
                    walk(value, key_path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                item_path = f"{path}[{index}]" if path else f"[{index}]"
                walk(item, item_path)

    walk(payload)
    return entries[:120]


def _extract_pending_submission_payload(deps: Any) -> dict[str, Any] | None:
    pending: Any = None
    getter = getattr(deps, "get_registry_value", None)
    if callable(getter):
        pending = getter(_PENDING_SUBMISSION_KEY)
    elif isinstance(getattr(deps, "registry", None), dict):
        pending = deps.registry.get(_PENDING_SUBMISSION_KEY)

    if not isinstance(pending, dict):
        memory = getattr(deps, "memory", None)
        memory_getter = getattr(memory, "get_kv", None)
        if callable(memory_getter):
            pending = memory_getter(_PENDING_SUBMISSION_KEY)

    return pending if isinstance(pending, dict) else None


def _normalize_submission_draft_payload(
    raw_submission_draft: dict[str, Any],
    *,
    draft: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    validation_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    process_label_raw = raw_submission_draft.get("process_label")
    process_label = process_label_raw.strip() if isinstance(process_label_raw, str) and process_label_raw.strip() else None
    if process_label is None and isinstance(draft, dict):
        process_label = _extract_process_label(draft)
    if process_label is None:
        process_label = "AiiDA Workflow"

    inputs = raw_submission_draft.get("inputs")
    if not isinstance(inputs, dict):
        inputs = _extract_submission_inputs(draft) if isinstance(draft, dict) else {}
    primary_inputs = raw_submission_draft.get("primary_inputs")
    if not isinstance(primary_inputs, dict):
        primary_inputs = _extract_primary_inputs(inputs)

    raw_advanced_settings = raw_submission_draft.get("advanced_settings")
    advanced_settings: dict[str, Any]
    if isinstance(raw_advanced_settings, dict):
        advanced_settings = {}
        for key, value in raw_advanced_settings.items():
            lowered = str(key).strip().lower()
            if lowered not in _CRITICAL_ADVANCED_KEYS:
                continue
            if _is_empty_submission_value(value) or _is_default_advanced_setting(lowered, value):
                continue
            advanced_settings[lowered] = value
    else:
        advanced_settings = _collect_advanced_settings(inputs)

    raw_meta = raw_submission_draft.get("meta")
    meta: dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    raw_recommended_inputs = raw_submission_draft.get("recommended_inputs")
    if not isinstance(raw_recommended_inputs, dict):
        meta_recommended = meta.get("recommended_inputs")
        raw_recommended_inputs = meta_recommended if isinstance(meta_recommended, dict) else None
    recommended_inputs = _normalize_recommended_inputs(raw_recommended_inputs, advanced_settings)
    meta["recommended_inputs"] = recommended_inputs
    raw_pk_map = meta.get("pk_map")
    if isinstance(raw_pk_map, list):
        normalized_pk_map: list[dict[str, Any]] = []
        seen: set[tuple[int, str]] = set()
        for item in raw_pk_map:
            if not isinstance(item, dict):
                continue
            pk = _coerce_positive_int(item.get("pk"))
            if pk is None:
                continue
            path_value = item.get("path")
            path = str(path_value).strip() if isinstance(path_value, str) and path_value.strip() else f"pk_{pk}"
            dedupe_key = (pk, path)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized_pk_map.append(
                {
                    "pk": pk,
                    "path": path,
                    "label": str(item.get("label") or "pk"),
                }
            )
        meta["pk_map"] = normalized_pk_map
    else:
        meta["pk_map"] = _collect_pk_map(inputs)

    if isinstance(draft, dict):
        meta["draft"] = draft
        meta.setdefault("target_computer", _extract_target_computer(draft))
        meta.setdefault("parallel_settings", _extract_parallel_settings(draft))
    parallel_settings = meta.get("parallel_settings")
    if not isinstance(parallel_settings, dict):
        parallel_settings = _extract_parallel_settings(draft) if isinstance(draft, dict) else {}
    meta["parallel_settings"] = parallel_settings
    if "target_computer" not in meta:
        meta["target_computer"] = _extract_target_computer(draft) if isinstance(draft, dict) else None
    meta.setdefault("workchain", process_label)
    for key, value in parallel_settings.items():
        lowered = str(key).strip().lower()
        if lowered in advanced_settings:
            continue
        if _is_empty_submission_value(value) or _is_default_advanced_setting(lowered, value):
            continue
        advanced_settings[lowered] = value
    if isinstance(validation, dict):
        meta["validation"] = validation
    if isinstance(validation_summary, dict):
        meta["validation_summary"] = validation_summary

    payload = {
        "process_label": process_label,
        "inputs": inputs,
        "primary_inputs": primary_inputs,
        "recommended_inputs": recommended_inputs,
        "advanced_settings": advanced_settings,
        "meta": meta,
    }
    return enrich_submission_draft_payload(payload)


def _build_submission_draft_payload(
    draft: dict[str, Any],
    *,
    validation: dict[str, Any] | None,
    validation_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    inputs = _extract_submission_inputs(draft)
    advanced_settings = _collect_advanced_settings(inputs)
    parallel_settings = _extract_parallel_settings(draft)
    for key, value in parallel_settings.items():
        if key in advanced_settings:
            continue
        if _is_empty_submission_value(value) or _is_default_advanced_setting(key, value):
            continue
        advanced_settings[key] = value
    recommended_inputs = _normalize_recommended_inputs(None, advanced_settings)
    process_label = _extract_process_label(draft)
    meta: dict[str, Any] = {
        "pk_map": _collect_pk_map(inputs),
        "target_computer": _extract_target_computer(draft),
        "parallel_settings": parallel_settings,
        "draft": draft,
        "recommended_inputs": recommended_inputs,
        "workchain": process_label,
    }
    if isinstance(validation, dict):
        meta["validation"] = validation
    if isinstance(validation_summary, dict):
        meta["validation_summary"] = validation_summary
    payload = {
        "process_label": process_label,
        "inputs": inputs,
        "primary_inputs": _extract_primary_inputs(inputs),
        "recommended_inputs": recommended_inputs,
        "advanced_settings": advanced_settings,
        "meta": meta,
    }
    return enrich_submission_draft_payload(payload)


def _extract_balanced_json_object(fragment: str) -> str | None:
    start = fragment.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(fragment)):
        char = fragment[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char != "}":
            continue

        depth -= 1
        if depth == 0:
            return fragment[start : index + 1]

    return None


def _extract_submission_draft_from_output_payload(output_payload: dict[str, Any]) -> dict[str, Any] | None:
    payload_type = str(output_payload.get("type") or "").strip().upper()
    status_type = str(output_payload.get("status") or "").strip().upper()
    raw_submission = output_payload.get("submission_draft")
    if isinstance(raw_submission, dict):
        return _normalize_submission_draft_payload(
            raw_submission,
            draft=None,
            validation=None,
            validation_summary=None,
        )
    raw_submission_tag = output_payload.get("submission_draft_tag")
    if isinstance(raw_submission_tag, str) and raw_submission_tag.strip():
        parsed_from_tag = _extract_submission_draft_from_text(raw_submission_tag)
        if isinstance(parsed_from_tag, dict):
            return parsed_from_tag
    raw_draft = output_payload.get("draft")
    if isinstance(raw_draft, dict):
        validation = output_payload.get("validation")
        validation_summary = output_payload.get("validation_summary")
        return _build_submission_draft_payload(
            raw_draft,
            validation=validation if isinstance(validation, dict) else None,
            validation_summary=validation_summary if isinstance(validation_summary, dict) else None,
        )
    if payload_type == "SUBMISSION_DRAFT":
        return _normalize_submission_draft_payload(
            output_payload,
            draft=None,
            validation=None,
            validation_summary=None,
        )
    if status_type == "SUBMISSION_DRAFT":
        return _normalize_submission_draft_payload(
            output_payload,
            draft=raw_draft if isinstance(raw_draft, dict) else None,
            validation=output_payload.get("validation") if isinstance(output_payload.get("validation"), dict) else None,
            validation_summary=(
                output_payload.get("validation_summary")
                if isinstance(output_payload.get("validation_summary"), dict)
                else None
            ),
        )
    return None


def _extract_submission_draft_from_text(answer_text: str | None) -> dict[str, Any] | None:
    text = str(answer_text or "")
    if not text.strip():
        return None

    tag_index = text.upper().rfind(_SUBMISSION_DRAFT_PREFIX)
    if tag_index < 0:
        return None

    fragment = text[tag_index + len(_SUBMISSION_DRAFT_PREFIX) :]
    json_text = _extract_balanced_json_object(fragment)
    if not json_text:
        logger.warning(
            log_event(
                "aiida.chat_turn.submission_draft_parse_failed",
                reason="incomplete_json_object",
                fragment_hash=_draft_fragment_hash(fragment),
                fragment_chars=len(fragment),
            )
        )
        return None

    try:
        parsed = json.loads(json_text)
    except Exception:  # noqa: BLE001
        logger.warning(
            log_event(
                "aiida.chat_turn.submission_draft_parse_failed",
                reason="invalid_json",
                fragment_hash=_draft_fragment_hash(fragment),
                fragment_chars=len(fragment),
            )
        )
        return None

    if not isinstance(parsed, dict):
        logger.warning(
            log_event(
                "aiida.chat_turn.submission_draft_parse_failed",
                reason="parsed_payload_not_object",
                fragment_hash=_draft_fragment_hash(fragment),
                fragment_chars=len(fragment),
            )
        )
        return None
    raw_submission = parsed.get("submission_draft") if isinstance(parsed.get("submission_draft"), dict) else parsed
    if not isinstance(raw_submission, dict):
        logger.warning(
            log_event(
                "aiida.chat_turn.submission_draft_parse_failed",
                reason="submission_draft_not_object",
                fragment_hash=_draft_fragment_hash(fragment),
                fragment_chars=len(fragment),
            )
        )
        return None
    return _normalize_submission_draft_payload(
        raw_submission,
        draft=None,
        validation=None,
        validation_summary=None,
    )


def _build_chat_message_payload(
    output: Any,
    deps: Any,
    *,
    tool_calls: list[str] | None = None,
    answer_text: str | None = None,
) -> dict[str, Any] | None:
    combined: dict[str, Any] = {}
    output_payload = getattr(output, "data_payload", None)
    if isinstance(output_payload, dict):
        combined["data_payload"] = output_payload
    if tool_calls:
        normalized_calls: list[str] = []
        for call in tool_calls:
            cleaned = str(call).strip()
            if not cleaned:
                continue
            if normalized_calls and normalized_calls[-1] == cleaned:
                continue
            normalized_calls.append(cleaned)
        if normalized_calls:
            combined["tool_calls"] = normalized_calls

    parsed_submission_draft_from_text = _extract_submission_draft_from_text(answer_text)

    resolved_submission_draft: dict[str, Any] | None = None
    pending = _extract_pending_submission_payload(deps)
    draft = pending.get("draft") if isinstance(pending, dict) else None
    validation = pending.get("validation") if isinstance(pending, dict) else None
    validation_summary = pending.get("validation_summary") if isinstance(pending, dict) else None
    raw_submission_draft = pending.get("submission_draft") if isinstance(pending, dict) else None
    if isinstance(raw_submission_draft, dict) or isinstance(draft, dict):
        if isinstance(raw_submission_draft, dict):
            resolved_submission_draft = _normalize_submission_draft_payload(
                raw_submission_draft,
                draft=draft if isinstance(draft, dict) else None,
                validation=validation if isinstance(validation, dict) else None,
                validation_summary=validation_summary if isinstance(validation_summary, dict) else None,
            )
        elif isinstance(draft, dict):
            resolved_submission_draft = _build_submission_draft_payload(
                draft,
                validation=validation if isinstance(validation, dict) else None,
                validation_summary=validation_summary if isinstance(validation_summary, dict) else None,
            )
    elif isinstance(output_payload, dict):
        resolved_submission_draft = _extract_submission_draft_from_output_payload(output_payload)

    if resolved_submission_draft is None:
        resolved_submission_draft = parsed_submission_draft_from_text

    if isinstance(resolved_submission_draft, dict):
        combined["type"] = "SUBMISSION_DRAFT"
        combined["submission_draft"] = resolved_submission_draft

    return combined or None


def _build_submission_draft_text_block(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    payload_type = str(payload.get("type") or "").strip().upper()
    if payload_type != "SUBMISSION_DRAFT":
        return None

    draft = payload.get("submission_draft")
    if not isinstance(draft, dict):
        return None

    try:
        serialized = json.dumps(draft, ensure_ascii=True, indent=2)
    except Exception:  # noqa: BLE001
        return None
    return f"{_SUBMISSION_DRAFT_PREFIX}\n{serialized}"


def _append_assistant_message(
    state: Any,
    turn_id: int,
    text: str,
    status: str = "done",
    *,
    payload: dict[str, Any] | None = None,
) -> None:
    chat_history = get_chat_history(state)
    message = {
        "role": "assistant",
        "text": text,
        "status": status,
        "turn_id": turn_id,
    }
    if isinstance(payload, dict):
        message["payload"] = payload
    chat_history.append(message)
    touch_chat(state)
    logger.info(
        log_event(
            "aiida.chat_turn.message_append",
            turn_id=turn_id,
            status=status,
            chars=len(text),
            has_payload=bool(payload),
        )
    )


def _to_agent_model_name(name: str) -> str:
    if ":" in name:
        return name
    return f"google-gla:{name}"


def _build_agent_model(name: str) -> Any:
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("Model name cannot be empty.")
    model_name = cleaned.split(":", 1)[1] if ":" in cleaned else cleaned

    api_version = str(getattr(settings, "GEMINI_API_VERSION", "") or "").strip()
    if not api_version:
        return _to_agent_model_name(cleaned)

    try:
        from google.genai import Client as GoogleGenAIClient
        from google.genai.types import HttpOptions
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider
    except Exception:  # noqa: BLE001
        logger.warning(
            log_event(
                "aiida.chat_turn.model_init_api_version_fallback",
                model=model_name,
                api_version=api_version,
            )
        )
        return _to_agent_model_name(cleaned)

    api_key = settings.GEMINI_API_KEY
    if api_key == "your-key-here":
        api_key = None

    client = GoogleGenAIClient(
        api_key=api_key,
        vertexai=False,
        http_options=HttpOptions(api_version=api_version),
    )
    provider = GoogleProvider(client=client)
    return GoogleModel(model_name, provider=provider)


def _build_model_settings() -> ModelSettings | None:
    max_tokens = int(getattr(settings, "GEMINI_MAX_OUTPUT_TOKENS", 0) or 0)
    if max_tokens <= 0:
        return None
    return ModelSettings(max_tokens=max_tokens)


def _get_model_unavailable_retry_policy() -> tuple[int, float]:
    retry_budget = int(getattr(settings, "GEMINI_UNAVAILABLE_RETRIES", 2) or 0)
    retry_budget = max(0, min(retry_budget, 8))
    base_backoff_seconds = float(
        getattr(settings, "GEMINI_UNAVAILABLE_RETRY_BACKOFF_SECONDS", 2.0) or 2.0
    )
    base_backoff_seconds = max(0.2, min(base_backoff_seconds, 60.0))
    return retry_budget, base_backoff_seconds


def _error_text_blob(error: Exception) -> str:
    values: list[str] = [str(error)]
    for attr in ("message", "body", "payload", "details", "status", "response"):
        value = getattr(error, attr, None)
        if value is None:
            continue
        values.append(str(value))
    return " ".join(value for value in values if value).lower()


def _is_retryable_model_unavailable_error(error: Exception) -> bool:
    text = _error_text_blob(error)
    if not text:
        return False

    has_503 = (
        "status_code: 503" in text
        or "status code: 503" in text
        or '"code": 503' in text
        or "'code': 503" in text
        or "http 503" in text
    )
    has_unavailable_hint = (
        "status': 'unavailable'" in text
        or '"status": "unavailable"' in text
        or "currently experiencing high demand" in text
        or "high demand" in text
        or "try again later" in text
        or "temporarily unavailable" in text
    )
    return has_503 and has_unavailable_hint


def _merge_context_node_ids(
    context_node_ids: list[int] | None,
    metadata: dict[str, Any] | None,
) -> list[int]:
    raw_ids: list[Any] = []
    if context_node_ids:
        raw_ids.extend(context_node_ids)
    if isinstance(metadata, dict):
        raw_ids.extend(normalize_context_node_ids(metadata.get("context_pks")))
        raw_ids.extend(normalize_context_node_ids(metadata.get("context_node_pks")))
    return normalize_context_node_ids(raw_ids)


def _inject_context_priority_instruction(user_intent: str, context_pks: list[int]) -> str:
    if not context_pks:
        return user_intent
    serialized = ", ".join(str(pk) for pk in context_pks)
    return (
        "PRIMARY TURN CONTEXT:\n"
        f"- context_pks: [{serialized}]\n"
        "- Treat these PKs as the primary subjects of the current user query.\n"
        "- If the request is ambiguous, prioritize inspecting these nodes first.\n\n"
        f"USER REQUEST:\n{user_intent}"
    )


async def _thinking_status_ticker(
    state: Any,
    turn_id: int,
    stop_event: asyncio.Event,
    get_running_tools: Callable[[], list[str]] | None = None,
    get_step_history: Callable[[], list[str]] | None = None,
) -> None:
    started = time.perf_counter()
    dots = 0
    while not stop_event.is_set():
        elapsed = int(time.perf_counter() - started)
        dots = (dots % 3) + 1
        status_lines = [f"Thinking: waiting for Gemini response ({elapsed}s){'.' * dots}"]
        running_tools: list[str] = []
        if callable(get_running_tools):
            running_tools = get_running_tools()
            if running_tools:
                status_lines.extend(f"Running: {tool_name}..." for tool_name in running_tools[-5:])
        step_history: list[str] = []
        if callable(get_step_history):
            step_history = get_step_history()

        status_payload = {
            "type": "status",
            "tool_calls": running_tools[-20:],
            "status": {
                "current_step": step_history[-1] if step_history else (running_tools[-1] if running_tools else None),
                "steps": step_history[-40:],
                "elapsed_seconds": elapsed,
            },
        }
        _update_assistant_message(
            state,
            turn_id,
            "\n".join(status_lines),
            status="thinking",
            payload=status_payload,
        )
        await asyncio.sleep(0.9)


def cancel_chat_turn(state: Any, turn_id: int | None = None) -> int | None:
    tasks = _ensure_chat_task_registry(state)
    if turn_id is not None:
        candidates = [(turn_id, tasks.get(turn_id))]
    else:
        candidates = sorted(tasks.items(), key=lambda item: item[0], reverse=True)

    for candidate_turn_id, task in candidates:
        if task is None:
            continue
        if task.done():
            tasks.pop(candidate_turn_id, None)
            continue
        task.cancel()
        _update_assistant_message(
            state,
            candidate_turn_id,
            "Response stopped by user.",
            status="error",
        )
        logger.info(log_event("aiida.chat_turn.cancel.requested", turn_id=candidate_turn_id))
        return candidate_turn_id

    return None


def start_chat_turn(
    state: Any,
    *,
    user_intent: str,
    selected_model: str,
    fetch_context_nodes: Callable[[list[int]], list[dict[str, Any]]],
    context_archive: str | None = None,
    context_node_ids: list[int] | None = None,
    metadata: dict[str, Any] | None = None,
    source: str = "frontend",
) -> int:
    chat_history = get_chat_history(state)
    normalized_metadata = dict(metadata or {})
    normalized_node_ids = _merge_context_node_ids(context_node_ids, normalized_metadata)
    normalized_metadata["context_pks"] = normalized_node_ids
    normalized_metadata["context_node_pks"] = normalized_node_ids
    turn_id = getattr(state, "chat_turn_seq", 0) + 1
    state.chat_turn_seq = turn_id

    user_message: dict[str, Any] = {"role": "user", "text": user_intent, "turn_id": turn_id}
    user_payload = _build_user_message_payload(normalized_metadata, normalized_node_ids)
    if isinstance(user_payload, dict):
        user_message["payload"] = user_payload
    chat_history.append(user_message)
    chat_history.append(
        {
            "role": "assistant",
            "text": "Thinking: request queued.",
            "status": "thinking",
            "turn_id": turn_id,
            "payload": {
                "type": "status",
                "status": {
                    "current_step": "Queued request",
                    "steps": [],
                },
                "tool_calls": [],
            },
        }
    )
    touch_chat(state)

    logger.info(
        log_event(
            "aiida.chat_turn.queued",
            turn_id=turn_id,
            source=source,
            model=selected_model,
            intent=user_intent[:120],
            context=context_archive,
            context_node_ids=",".join(str(pk) for pk in normalized_node_ids) or None,
            metadata_keys=",".join(sorted(str(key) for key in normalized_metadata.keys())) or None,
        )
    )

    task = asyncio.create_task(
        _execute_chat_turn(
            state=state,
            turn_id=turn_id,
            user_intent=user_intent,
            selected_model=selected_model,
            fetch_context_nodes=fetch_context_nodes,
            context_archive=context_archive,
            context_node_ids=normalized_node_ids,
            metadata=normalized_metadata,
        )
    )
    _ensure_chat_task_registry(state)[turn_id] = task
    task.add_done_callback(
        lambda _task, _state=state, _turn_id=turn_id: _ensure_chat_task_registry(_state).pop(_turn_id, None)
    )
    return turn_id


async def _execute_chat_turn(
    state: Any,
    turn_id: int,
    user_intent: str,
    selected_model: str,
    fetch_context_nodes: Callable[[list[int]], list[dict[str, Any]]],
    context_archive: str | None = None,
    context_node_ids: list[int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    agent = getattr(state, "agent", None)
    deps_class = getattr(state, "deps_class", None)
    lock = _ensure_chat_lock(state)
    t0 = time.perf_counter()
    spinner_stop = asyncio.Event()
    spinner_task: asyncio.Task | None = None
    bridge_tool_calls: list[str] = []

    def _record_bridge_call(tool_name: str) -> None:
        cleaned = str(tool_name).strip()
        if not cleaned:
            return
        if bridge_tool_calls and bridge_tool_calls[-1] == cleaned:
            return
        bridge_tool_calls.append(cleaned)
        if len(bridge_tool_calls) > 40:
            del bridge_tool_calls[:-40]

    async with lock:
        logger.info(
            log_event(
                "aiida.chat_turn.start",
                turn_id=turn_id,
                model=selected_model,
                intent=user_intent[:120],
                context=context_archive,
                context_node_ids=",".join(str(pk) for pk in normalize_context_node_ids(context_node_ids)) or None,
                metadata_keys=",".join(sorted(str(key) for key in (metadata or {}).keys())) or None,
            )
        )

        try:
            if agent is None or deps_class is None:
                raise RuntimeError("Agent dependencies are not ready")

            normalized_node_ids = _merge_context_node_ids(context_node_ids, metadata)
            context_nodes = fetch_context_nodes(normalized_node_ids)
            if context_nodes:
                _update_assistant_message(
                    state,
                    turn_id,
                    f"Thinking: loaded {len(context_nodes)} referenced nodes...",
                    status="thinking",
                )

            deps_kwargs: dict[str, Any] = {
                "archive_path": context_archive,
                "memory": getattr(state, "memory", None),
            }
            if "context_nodes" in getattr(deps_class, "__annotations__", {}):
                deps_kwargs["context_nodes"] = context_nodes
            current_deps = deps_class(**deps_kwargs)
            step_history: list[str] = getattr(current_deps, "step_history", [])

            def _record_step_update(step_text: str) -> None:
                cleaned = str(step_text).strip()
                if not cleaned:
                    return
                payload = {
                    "type": "status",
                    "tool_calls": bridge_tool_calls[-20:],
                    "status": {
                        "current_step": cleaned,
                        "steps": step_history[-40:],
                    },
                }
                _update_assistant_message(
                    state,
                    turn_id,
                    None,
                    status="thinking",
                    payload=payload,
                )

            if hasattr(current_deps, "step_callback"):
                setattr(current_deps, "step_callback", _record_step_update)

            listener_token = set_bridge_call_listener(_record_bridge_call)
            spinner_task = asyncio.create_task(
                _thinking_status_ticker(
                    state=state,
                    turn_id=turn_id,
                    stop_event=spinner_stop,
                    get_running_tools=lambda: list(bridge_tool_calls),
                    get_step_history=lambda: list(step_history),
                )
            )
            try:
                run_intent = _inject_context_priority_instruction(user_intent, normalized_node_ids)
                resolved_model_name = _to_agent_model_name(selected_model)
                resolved_model = _build_agent_model(selected_model)
                retry_budget, retry_base_backoff_seconds = _get_model_unavailable_retry_policy()
                last_run_error: Exception | None = None
                result = None
                for attempt in range(retry_budget + 1):
                    try:
                        result = await agent.run(
                            run_intent,
                            deps=current_deps,
                            model=resolved_model,
                            model_settings=_build_model_settings(),
                        )
                        last_run_error = None
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as run_error:  # noqa: BLE001
                        error_text = str(run_error)
                        normalized_error = error_text.lower()
                        if (
                            "404" in normalized_error
                            and "model" in normalized_error
                            or "is not found for api version" in normalized_error
                            or "unsupported model" in normalized_error
                        ):
                            logger.error(
                                log_event(
                                    "aiida.chat_turn.model_rejected",
                                    turn_id=turn_id,
                                    model=selected_model,
                                    resolved_model=resolved_model_name,
                                    api_version=getattr(settings, "GEMINI_API_VERSION", "unknown"),
                                    error=error_text[:500],
                                )
                            )
                            raise RuntimeError(
                                "Gemini model was rejected by the API. "
                                f"Model='{selected_model}', api_version='{getattr(settings, 'GEMINI_API_VERSION', 'unknown')}'. "
                                "Update SABR_DEFAULT_MODEL (e.g., gemini-3-flash-preview) "
                                "or SABR_GEMINI_API_VERSION and retry."
                            ) from run_error

                        if _is_retryable_model_unavailable_error(run_error) and attempt < retry_budget:
                            wait_seconds = retry_base_backoff_seconds * (2**attempt)
                            retry_step = (
                                "Gemini is under high demand (503). "
                                f"Auto-retrying in {wait_seconds:.1f}s ({attempt + 1}/{retry_budget})."
                            )
                            current_deps.log_step(retry_step)
                            logger.warning(
                                log_event(
                                    "aiida.chat_turn.model_unavailable_retry",
                                    turn_id=turn_id,
                                    model=selected_model,
                                    attempt=attempt + 1,
                                    max_attempts=retry_budget + 1,
                                    wait_seconds=f"{wait_seconds:.2f}",
                                    error=error_text[:500],
                                )
                            )
                            await asyncio.sleep(wait_seconds)
                            continue

                        last_run_error = run_error
                        break

                if result is None:
                    if last_run_error is None:
                        raise RuntimeError("Model call failed: no result and no error captured.")
                    if _is_retryable_model_unavailable_error(last_run_error):
                        logger.error(
                            log_event(
                                "aiida.chat_turn.model_unavailable_retry_exhausted",
                                turn_id=turn_id,
                                model=selected_model,
                                attempts=retry_budget + 1,
                                error=str(last_run_error)[:500],
                            )
                        )
                    raise last_run_error
            finally:
                reset_bridge_call_listener(listener_token)

            spinner_stop.set()
            if spinner_task:
                spinner_task.cancel()
                with suppress(asyncio.CancelledError):
                    await spinner_task
                spinner_task = None

            elapsed = time.perf_counter() - t0
            output = getattr(result, "output", None)
            if output is None:
                output = getattr(result, "data", None)
            if output is None:
                raise RuntimeError("Agent returned no output payload")

            if hasattr(current_deps, "step_history") and hasattr(output, "thought_process"):
                output.thought_process = current_deps.step_history

            answer_text = str(output.answer) if hasattr(output, "answer") else str(output)
            message_payload = _build_chat_message_payload(
                output,
                current_deps,
                tool_calls=bridge_tool_calls,
                answer_text=answer_text,
            )
            submission_draft_block = _build_submission_draft_text_block(message_payload)
            if submission_draft_block:
                has_submission_prefix = _SUBMISSION_DRAFT_PREFIX.lower() in answer_text.lower()
                has_canonical_block = submission_draft_block in answer_text
                if not has_submission_prefix:
                    answer_text = (
                        f"{answer_text.rstrip()}\n\n{submission_draft_block}"
                        if answer_text.strip()
                        else submission_draft_block
                    )
                elif not has_canonical_block:
                    # Ensure at least one parse-safe canonical draft block exists for the frontend modal parser.
                    answer_text = f"{answer_text.rstrip()}\n\n{submission_draft_block}"
            _append_assistant_message(
                state,
                turn_id,
                answer_text,
                status="done",
                payload=message_payload,
            )
            state.chat_history = get_chat_history(state)[-200:]
            touch_chat(state)
            logger.info(
                log_event(
                    "aiida.chat_turn.done",
                    turn_id=turn_id,
                    run_id=getattr(result, "run_id", None),
                    elapsed=f"{elapsed:.2f}s",
                    answer_chars=len(answer_text),
                    steps=len(getattr(current_deps, "step_history", []) or []),
                )
            )

            if hasattr(state, "memory") and state.memory:
                try:
                    turn_metadata: dict[str, Any] = {
                        "context_archive": context_archive,
                        "context_node_ids": normalized_node_ids,
                    }
                    for key, value in (metadata or {}).items():
                        turn_metadata[str(key)] = value
                    state.memory.add_turn(
                        intent=user_intent,
                        response=answer_text,
                        metadata=turn_metadata,
                    )
                except Exception as mem_error:  # noqa: BLE001
                    logger.warning(
                        log_event(
                            "aiida.chat_turn.persist_failed",
                            turn_id=turn_id,
                            error=str(mem_error),
                        )
                    )

        except asyncio.CancelledError:
            elapsed = time.perf_counter() - t0
            _update_assistant_message(
                state,
                turn_id,
                "Response stopped by user.",
                status="error",
            )
            state.chat_history = get_chat_history(state)[-200:]
            touch_chat(state)
            logger.info(
                log_event(
                    "aiida.chat_turn.cancelled",
                    turn_id=turn_id,
                    elapsed=f"{elapsed:.2f}s",
                    model=selected_model,
                )
            )
            raise
        except Exception as error:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            logger.exception(
                log_event(
                    "aiida.chat_turn.failed",
                    turn_id=turn_id,
                    elapsed=f"{elapsed:.2f}s",
                    model=selected_model,
                    error=str(error),
                )
            )
            _append_assistant_message(
                state,
                turn_id,
                f"Request failed: {error}",
                status="error",
            )
            state.chat_history = get_chat_history(state)[-200:]
            touch_chat(state)
        finally:
            spinner_stop.set()
            if spinner_task:
                spinner_task.cancel()
                with suppress(asyncio.CancelledError):
                    await spinner_task
