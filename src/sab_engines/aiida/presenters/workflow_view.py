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
            "ui_type": _infer_ui_type(path, value),
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
                "ui_type": _infer_ui_type(key, value),
            },
        )

    return all_inputs


_INPUT_GROUP_ORDER = (
    "computational_details",
    "brillouin_zone",
    "system_environment",
    "physics_protocol",
)

_INPUT_GROUP_TITLE = {
    "computational_details": "Computational Details",
    "brillouin_zone": "Brillouin Zone",
    "system_environment": "System Environment",
    "physics_protocol": "Physics Protocol",
}


def _format_label(value: str) -> str:
    return value.replace("_", " ").replace(".", " ").strip().title()


def _looks_like_mesh_path(path: str) -> bool:
    lowered = _normalize_key(path)
    if "kpoint" not in lowered and "kpoints" not in lowered:
        return False
    return lowered.endswith(".mesh") or ".mesh." in lowered or lowered.endswith("_mesh")


def _is_mesh_triplet(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 3:
        return False
    for item in value:
        if isinstance(item, bool):
            return False
        if not isinstance(item, (int, float)):
            return False
    return True


def _infer_ui_type(path: str, value: Any) -> str:
    if _looks_like_mesh_path(path) or _is_mesh_triplet(value):
        return "mesh"
    if isinstance(value, bool):
        return "toggle"
    if isinstance(value, (dict, list)):
        return "dict"
    return "scalar"


def _classify_port_group(path: str) -> str:
    lowered = _normalize_key(path)
    leaf = lowered.rsplit(".", 1)[-1]

    if (
        "metadata.options" in lowered
        or ".resources." in lowered
        or leaf in {"resources", "metadata_options", "max_wallclock_seconds", "queue_name", "account"}
    ):
        return "system_environment"
    if "kpoint" in lowered or "kpoints" in lowered or leaf in {"mesh", "kpoints_distance", "kpoint_distance"}:
        return "brillouin_zone"
    if any(
        token in lowered
        for token in (
            "relax_type",
            "protocol",
            "pseudo_family",
            "pseudopotential",
            "electronic_type",
            "spin_type",
        )
    ):
        return "physics_protocol"
    if ".parameters" in lowered or lowered.startswith("parameters") or "pw.parameters" in lowered:
        return "computational_details"
    return "computational_details"


def _derive_port_path(path: str, group_id: str) -> str:
    segments = [segment for segment in str(path).split(".") if segment]
    lowered = [segment.lower() for segment in segments]

    if group_id == "system_environment":
        for index in range(len(segments) - 1):
            if lowered[index] == "metadata" and lowered[index + 1] == "options":
                base = segments[: index + 2]
                if index + 2 < len(segments) and lowered[index + 2] == "resources":
                    base.append(segments[index + 2])
                return ".".join(base)
        for index, segment in enumerate(lowered):
            if segment in {"resources", "queue_name", "max_wallclock_seconds", "account"}:
                return ".".join(segments[: index + 1])

    if group_id == "computational_details":
        for index, segment in enumerate(lowered):
            if segment == "parameters":
                return ".".join(segments[: index + 1])

    if group_id == "brillouin_zone":
        for index, segment in enumerate(lowered):
            if "kpoint" in segment:
                return ".".join(segments[: index + 1])
        for index, segment in enumerate(lowered):
            if segment == "mesh":
                return ".".join(segments[: index + 1])

    if group_id == "physics_protocol":
        for index, segment in enumerate(lowered):
            if segment in {"relax_type", "protocol", "pseudo_family", "pseudo_family_label"}:
                return ".".join(segments[: index + 1])

    if len(segments) <= 1:
        return path
    return ".".join(segments[:-1])


def _editor_hint(path: str, ui_type: str) -> str | None:
    lowered = _normalize_key(path)
    if ui_type == "mesh":
        return "mesh"
    if "metadata.options.resources" in lowered:
        return "resource_grid"
    if ui_type == "dict":
        return "property_grid"
    return None


def _build_input_groups(all_inputs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_ports: dict[tuple[str, str], dict[str, Any]] = {}

    for path, raw_entry in all_inputs.items():
        entry = _as_dict(raw_entry) or {"value": raw_entry}
        value = entry.get("value")
        is_recommended = bool(entry.get("is_recommended"))
        ui_type = str(entry.get("ui_type") or _infer_ui_type(path, value))
        group_id = _classify_port_group(path)
        port_path = _derive_port_path(path, group_id)
        port_key = (group_id, port_path)
        port = grouped_ports.get(port_key)
        if port is None:
            port = {
                "path": port_path,
                "label": _format_label(port_path.split(".")[-1] if "." in port_path else port_path),
                "ui_type": "dict",
                "editor_hint": None,
                "is_recommended": False,
                "properties": [],
            }
            grouped_ports[port_key] = port

        property_key = path[len(port_path) :].lstrip(".") if path.startswith(f"{port_path}.") else path
        property_label = _format_label(property_key.split(".")[-1] if property_key else path.split(".")[-1])
        port["properties"].append(
            {
                "path": path,
                "key": property_key or path,
                "label": property_label,
                "value": value,
                "ui_type": ui_type,
                "editor_hint": _editor_hint(path, ui_type),
                "is_recommended": is_recommended,
            }
        )
        if is_recommended:
            port["is_recommended"] = True
        if ui_type == "mesh":
            port["ui_type"] = "mesh"
        elif len(port["properties"]) == 1:
            port["ui_type"] = ui_type
        else:
            port["ui_type"] = "dict"
        port["editor_hint"] = _editor_hint(port_path, str(port["ui_type"]))

    grouped_payload: list[dict[str, Any]] = []
    for group_id in _INPUT_GROUP_ORDER:
        ports = [
            value
            for (entry_group_id, _), value in grouped_ports.items()
            if entry_group_id == group_id and value.get("properties")
        ]
        if not ports:
            continue
        for port in ports:
            properties = port.get("properties")
            if isinstance(properties, list):
                properties.sort(key=lambda item: str(item.get("key") or ""))
        ports.sort(key=lambda port_entry: str(port_entry.get("path") or ""))
        grouped_payload.append(
            {
                "id": group_id,
                "title": _INPUT_GROUP_TITLE[group_id],
                "ports": ports,
            }
        )
    return grouped_payload


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


def _extract_messages(payload: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    raw_messages: list[str] = []
    for key in keys:
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = item.get("message") or item.get("error") or item.get("detail") or item.get("reason")
                    raw_messages.append(str(text if text is not None else item))
                else:
                    raw_messages.append(str(item))
            continue
        if isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, list):
                    raw_messages.extend(str(entry) for entry in nested)
                else:
                    raw_messages.append(str(nested))
            continue
        raw_messages.append(str(value))

    deduped: list[str] = []
    seen: set[str] = set()
    for message in raw_messages:
        cleaned = message.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _build_validation_summary(
    validation: dict[str, Any] | None,
    existing_summary: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(validation, dict) and not isinstance(existing_summary, dict):
        return None

    summary_seed = dict(existing_summary) if isinstance(existing_summary, dict) else {}
    validation_payload = validation if isinstance(validation, dict) else {}
    errors = summary_seed.get("errors")
    warnings = summary_seed.get("warnings")
    if not isinstance(errors, list):
        errors = _extract_messages(
            validation_payload,
            ("error", "errors", "validation_errors", "blocking_errors", "missing_inputs", "missing"),
        )
    else:
        errors = [str(item).strip() for item in errors if str(item).strip()]

    if not isinstance(warnings, list):
        warnings = _extract_messages(
            validation_payload,
            ("warnings", "validation_warnings", "non_blocking_warnings"),
        )
    else:
        warnings = [str(item).strip() for item in warnings if str(item).strip()]

    status_raw = summary_seed.get("status", validation_payload.get("status"))
    status = str(status_raw).strip() if status_raw is not None else ""
    status_upper = status.upper()
    is_valid_field = summary_seed.get("is_valid", validation_payload.get("is_valid"))
    if isinstance(is_valid_field, bool):
        is_valid = is_valid_field
    elif status_upper in {"VALID", "VALIDATION_OK", "OK", "SUCCESS", "PASSED"}:
        is_valid = True
    elif status_upper in {"INVALID", "VALIDATION_FAILED", "FAILED", "ERROR"}:
        is_valid = False
    else:
        is_valid = len(errors) == 0

    normalized_status = status or ("VALIDATION_OK" if is_valid else "VALIDATION_FAILED")
    blocking_error_count_raw = summary_seed.get("blocking_error_count")
    warning_count_raw = summary_seed.get("warning_count")
    try:
        blocking_error_count = int(blocking_error_count_raw) if blocking_error_count_raw is not None else len(errors)
    except (TypeError, ValueError):
        blocking_error_count = len(errors)
    try:
        warning_count = int(warning_count_raw) if warning_count_raw is not None else len(warnings)
    except (TypeError, ValueError):
        warning_count = len(warnings)

    summary_lines = [
        f"Status: {normalized_status}",
        f"Valid: {'yes' if is_valid else 'no'}",
        f"Blocking errors: {blocking_error_count}",
        f"Warnings: {warning_count}",
    ]
    if errors:
        summary_lines.append(f"Top error: {errors[0]}")
    if warnings:
        summary_lines.append(f"Top warning: {warnings[0]}")

    return {
        "status": normalized_status,
        "is_valid": is_valid,
        "blocking_error_count": max(0, blocking_error_count),
        "warning_count": max(0, warning_count),
        "errors": errors,
        "warnings": warnings,
        "summary_text": str(summary_seed.get("summary_text") or "\n".join(summary_lines)),
    }


def _coerce_validation_payload(validation_result: Any, *, entry_point: str) -> dict[str, Any]:
    if validation_result is None:
        return {
            "status": "VALIDATION_OK",
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "source": "spec.validate",
            "entry_point": entry_point,
        }

    if isinstance(validation_result, dict):
        payload = dict(validation_result)
        payload.setdefault("status", "VALIDATION_FAILED")
        payload.setdefault("is_valid", False)
        payload.setdefault("source", "spec.validate")
        payload.setdefault("entry_point", entry_point)
        return payload

    message = str(validation_result).strip() or "Builder inputs failed schema validation."
    return {
        "status": "VALIDATION_FAILED",
        "is_valid": False,
        "errors": [message],
        "warnings": [],
        "source": "spec.validate",
        "entry_point": entry_point,
    }


def _validate_builder_inputs(
    payload: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any] | None:
    meta = _as_dict(payload.get("meta")) or {}
    explicit_entry_points: list[str] = []
    for candidate in (
        meta.get("workchain"),
        meta.get("workchain_entry_point"),
        meta.get("entry_point"),
        payload.get("workchain"),
        payload.get("workchain_entry_point"),
        payload.get("entry_point"),
        payload.get("process_label"),
    ):
        if isinstance(candidate, str):
            cleaned = candidate.strip()
            if cleaned and cleaned not in explicit_entry_points:
                explicit_entry_points.append(cleaned)

    if not explicit_entry_points:
        return None

    try:
        from aiida.plugins import WorkflowFactory
    except Exception:
        return None

    for entry_point in explicit_entry_points:
        try:
            wc_class = WorkflowFactory(entry_point)
            validation_result = wc_class.spec().validate(inputs)
            return _coerce_validation_payload(validation_result, entry_point=entry_point)
        except Exception:
            continue
    return None


def enrich_submission_draft_payload(submission_draft: dict[str, Any]) -> dict[str, Any]:
    payload = dict(submission_draft)
    inputs = _as_dict(payload.get("inputs")) or {}
    recommended_inputs = _as_dict(payload.get("recommended_inputs"))
    if recommended_inputs is None:
        recommended_inputs = _as_dict(payload.get("advanced_settings")) or {}
        payload["recommended_inputs"] = recommended_inputs

    payload["all_inputs"] = _build_all_inputs(inputs, recommended_inputs)
    payload["input_groups"] = _build_input_groups(payload["all_inputs"])

    meta = _as_dict(payload.get("meta"))
    if meta is None:
        meta = {}
        payload["meta"] = meta

    if not isinstance(meta.get("recommended_inputs"), dict):
        meta["recommended_inputs"] = recommended_inputs
    if not isinstance(meta.get("input_groups"), list):
        meta["input_groups"] = payload["input_groups"]

    structure_metadata = _extract_structure_metadata_entries(payload)
    meta["structure_metadata"] = structure_metadata
    if structure_metadata:
        first = structure_metadata[0]
        meta.setdefault("symmetry", first.get("symmetry"))
        meta.setdefault("num_atoms", first.get("num_atoms"))
        meta.setdefault("estimated_runtime", first.get("estimated_runtime"))

    validation = _as_dict(meta.get("validation"))
    if validation is None:
        validation = _validate_builder_inputs(payload, inputs)
        if isinstance(validation, dict):
            meta["validation"] = validation

    validation_summary = _build_validation_summary(
        validation if isinstance(validation, dict) else None,
        _as_dict(meta.get("validation_summary")),
    )
    if isinstance(validation_summary, dict):
        meta["validation_summary"] = validation_summary

    return payload


__all__ = [
    "extract_submitted_pk",
    "format_single_submission_response",
    "format_batch_submission_response",
    "enrich_submission_draft_payload",
]
