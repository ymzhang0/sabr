from __future__ import annotations

from typing import Any


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def extract_submitted_pk(payload: Any) -> int | None:
    if isinstance(payload, bool) or payload is None:
        return None
    if isinstance(payload, (int, str)):
        return _coerce_int(payload)
    if isinstance(payload, list):
        for item in payload:
            candidate = extract_submitted_pk(item)
            if candidate is not None:
                return candidate
        return None

    if not isinstance(payload, dict):
        return None

    primary_keys = (
        "process_pk",
        "submitted_pk",
        "workflow_pk",
        "process_id",
        "process_node_pk",
        "pk",
        "id",
    )
    for key in primary_keys:
        candidate = _coerce_int(payload.get(key))
        if candidate is not None:
            return candidate

    array_keys = ("submitted_pks", "process_pks", "workflow_pks", "pks")
    for key in array_keys:
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            candidate = _coerce_int(item)
            if candidate is not None:
                return candidate

    for key in ("submission", "result", "data"):
        if key not in payload:
            continue
        candidate = extract_submitted_pk(payload.get(key))
        if candidate is not None:
            return candidate

    return None


def format_single_submission_response(raw: Any) -> dict[str, Any]:
    response = raw if isinstance(raw, dict) else {"result": raw}
    submitted_pk = extract_submitted_pk(response)
    response["submitted_pks"] = [submitted_pk] if submitted_pk is not None else []
    response["process_pks"] = [submitted_pk] if submitted_pk is not None else []
    return response


def format_batch_submission_response(
    submitted_pks: list[int],
    responses: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "SUBMITTED_BATCH",
        "submitted_pks": submitted_pks,
        "process_pks": submitted_pks,
        "responses": responses,
        "failures": failures,
    }


def _as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for entry in value:
        if isinstance(entry, dict):
            items.append(entry)
    return items


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower()


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _find_first_named_value(payload: Any, candidate_keys: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = _normalize_key(key)
            if lowered in candidate_keys and not _is_empty_value(value):
                return value
            nested = _find_first_named_value(value, candidate_keys)
            if nested is not None:
                return nested
    elif isinstance(payload, list):
        for entry in payload:
            nested = _find_first_named_value(entry, candidate_keys)
            if nested is not None:
                return nested
    return None


def _flatten_input_ports(payload: Any, *, prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    flattened = out if isinstance(out, dict) else {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key).strip()
            if not key_text:
                continue
            path = f"{prefix}.{key_text}" if prefix else key_text
            if isinstance(value, dict):
                _flatten_input_ports(value, prefix=path, out=flattened)
                continue
            flattened[path] = value
        return flattened

    if prefix:
        flattened[prefix] = payload
    return flattened


def _build_all_inputs(
    inputs: dict[str, Any],
    recommended_inputs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    flattened = _flatten_input_ports(inputs)
    recommended_set = {_normalize_key(key) for key in recommended_inputs.keys() if _normalize_key(key)}
    all_inputs: dict[str, dict[str, Any]] = {}

    for path, value in flattened.items():
        normalized_path = _normalize_key(path)
        leaf = normalized_path.rsplit(".", 1)[-1]
        is_recommended = normalized_path in recommended_set or leaf in recommended_set
        all_inputs[path] = {
            "value": value,
            "is_recommended": is_recommended,
        }

    for raw_key, value in recommended_inputs.items():
        key = str(raw_key).strip()
        if not key:
            continue
        all_inputs.setdefault(
            key,
            {
                "value": value,
                "is_recommended": True,
            },
        )

    return all_inputs


def _extract_symmetry(payload: Any) -> str | None:
    symmetry = _find_first_named_value(
        payload,
        {
            "symmetry",
            "symmetry_label",
            "spacegroup",
            "space_group",
            "space_group_symbol",
            "international_symbol",
            "crystal_system",
            "spglib",
        },
    )
    if isinstance(symmetry, dict):
        for key in (
            "international_symbol",
            "space_group_symbol",
            "spacegroup",
            "symbol",
            "crystal_system",
            "label",
            "name",
            "hall_symbol",
        ):
            value = symmetry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        number = _coerce_int(symmetry.get("number"))
        if number is not None:
            return f"Space group {number}"
        return None

    if isinstance(symmetry, str) and symmetry.strip():
        return symmetry.strip()
    number = _coerce_int(symmetry)
    if number is not None:
        return f"Space group {number}"
    return None


def _extract_estimated_runtime(payload: Any) -> Any:
    return _find_first_named_value(
        payload,
        {
            "estimated_runtime",
            "estimated_runtime_seconds",
            "runtime_estimate",
            "runtime_prediction",
            "runtime_seconds",
            "time_estimate",
            "time_estimate_seconds",
            "predicted_runtime_seconds",
            "max_wallclock_seconds",
        },
    )


def _extract_num_atoms(payload: Any) -> int | None:
    value = _find_first_named_value(
        payload,
        {
            "num_atoms",
            "natoms",
            "number_of_atoms",
            "sites",
            "nsites",
            "sites_count",
        },
    )
    return _coerce_int(value)


def _extract_structure_metadata_entries(submission_draft: dict[str, Any]) -> list[dict[str, Any]]:
    meta = _as_dict(submission_draft.get("meta")) or {}
    candidates: list[dict[str, Any]] = []

    meta_draft = meta.get("draft")
    if isinstance(meta_draft, dict):
        candidates.append(meta_draft)
    elif isinstance(meta_draft, list):
        candidates.extend(_as_dict_list(meta_draft))

    inputs = _as_dict(submission_draft.get("inputs")) or {}
    for key in ("jobs", "tasks", "submissions", "drafts"):
        candidates.extend(_as_dict_list(inputs.get(key)))

    if not candidates:
        candidates.append(inputs)

    entries: list[dict[str, Any]] = []
    seen: set[tuple[int | None, str]] = set()
    for index, candidate in enumerate(candidates):
        structure_value = _find_first_named_value(
            candidate,
            {"structure_pk", "structure_id", "structure", "pk"},
        )
        structure_record = _as_dict(structure_value)
        pk = (
            _coerce_int(structure_record.get("pk") if isinstance(structure_record, dict) else None)
            or _coerce_int(structure_record.get("structure_pk") if isinstance(structure_record, dict) else None)
            or _coerce_int(structure_value)
        )
        formula_value = _find_first_named_value(
            candidate,
            {"formula", "structure_label", "label", "name", "structure_name"},
        )
        formula = str(formula_value).strip() if isinstance(formula_value, str) and formula_value.strip() else None
        if formula is None and pk is not None:
            formula = f"Structure #{pk}"
        if formula is None:
            formula = f"Task {index + 1}"

        symmetry = _extract_symmetry(candidate)
        num_atoms = _extract_num_atoms(candidate)
        estimated_runtime = _extract_estimated_runtime(candidate)

        dedupe_key = (pk, formula)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        entries.append(
            {
                "pk": pk,
                "formula": formula,
                "symmetry": symmetry,
                "num_atoms": num_atoms,
                "estimated_runtime": estimated_runtime,
            }
        )

    return entries


def enrich_submission_draft_payload(submission_draft: dict[str, Any]) -> dict[str, Any]:
    payload = dict(submission_draft)
    inputs = _as_dict(payload.get("inputs")) or {}
    recommended_inputs = _as_dict(payload.get("recommended_inputs"))
    if recommended_inputs is None:
        recommended_inputs = _as_dict(payload.get("advanced_settings")) or {}
        payload["recommended_inputs"] = recommended_inputs

    payload["all_inputs"] = _build_all_inputs(inputs, recommended_inputs)

    meta = _as_dict(payload.get("meta"))
    if meta is None:
        meta = {}
        payload["meta"] = meta

    if not isinstance(meta.get("recommended_inputs"), dict):
        meta["recommended_inputs"] = recommended_inputs

    structure_metadata = _extract_structure_metadata_entries(payload)
    meta["structure_metadata"] = structure_metadata
    if structure_metadata:
        first = structure_metadata[0]
        meta.setdefault("symmetry", first.get("symmetry"))
        meta.setdefault("num_atoms", first.get("num_atoms"))
        meta.setdefault("estimated_runtime", first.get("estimated_runtime"))

    return payload


__all__ = [
    "extract_submitted_pk",
    "format_single_submission_response",
    "format_batch_submission_response",
    "enrich_submission_draft_payload",
]
