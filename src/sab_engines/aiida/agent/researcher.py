import json
from typing import Any

from loguru import logger
from pydantic_ai import Agent, RunContext

from src.sab_engines.aiida.deps import AiiDADeps
from src.sab_core.config import settings
from src.sab_engines.aiida.agent.prompts import (
    REFERENCED_NODES_HEADER,
    REFERENCED_NODES_INTRO,
    REFERENCED_NODES_OMITTED_TEMPLATE,
    SUBMISSION_DRAFT_NEXT_STEP_GUIDANCE,
    SUBMISSION_DRAFT_PREFIX,
    build_system_prompt,
)
from src.sab_engines.aiida.agent.tools import (
    draft_workchain_builder,
    fetch_recent_processes,
    get_bands_plot_data,
    get_database_summary,
    get_node_file_content,
    get_node_summary,
    get_remote_file_content,
    get_remote_workchain_spec as get_remote_workchain_spec_via_bridge,
    get_statistics,
    get_unified_source_map,
    inspect_group,
    inspect_lab_infrastructure as inspect_lab_infrastructure_via_bridge,
    inspect_process,
    inspect_workchain_spec,
    list_group_labels,
    list_groups,
    list_local_archives,
    list_remote_files,
    list_remote_plugins as list_remote_plugins_via_bridge,
    list_registered_skills_sync,
    list_system_profiles,
    register_specialized_skill,
    run_python_code,
    execute_specialized_skill,
    submit_job,
    switch_profile,
    validate_job,
)
from src.sab_engines.aiida.presenters.workflow_view import enrich_submission_draft_payload
from src.sab_core.logging_utils import log_event
from src.sab_core.schema.response import SABRResponse

_PENDING_SUBMISSION_KEY = "aiida_pending_submission"
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


def _load_specialized_skills_snapshot() -> list[dict[str, Any]]:
    payload = list_registered_skills_sync()
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "description": str(item.get("description") or "").strip() or None,
                "entrypoint": str(item.get("entrypoint") or "").strip() or "main(params)",
            }
        )
    return normalized


def _build_startup_skill_overlay(skills: list[dict[str, Any]]) -> list[str]:
    if not skills:
        return [
            "Startup skill registry snapshot: no specialized skills were discovered from worker /registry/list."
        ]
    lines = [
        "Startup skill registry snapshot from worker /registry/list (use call_specialized_skill for these):"
    ]
    for item in skills[:20]:
        description = item.get("description")
        if isinstance(description, str) and description.strip():
            lines.append(f"{item['name']}: {description.strip()}")
        else:
            lines.append(str(item["name"]))
    return lines


_STARTUP_SPECIALIZED_SKILLS = _load_specialized_skills_snapshot()
logger.info(
    log_event(
        "aiida.agent.skills.snapshot.loaded",
        discovered=len(_STARTUP_SPECIALIZED_SKILLS),
    )
)

aiida_researcher = Agent(
    f"google-gla:{settings.DEFAULT_MODEL}",
    deps_type=AiiDADeps,
    output_type=SABRResponse,
    system_prompt=build_system_prompt(
        extra_instructions=_build_startup_skill_overlay(_STARTUP_SPECIALIZED_SKILLS),
    ),
    retries=3,
)


def _format_context_node_line(node: dict[str, Any]) -> str:
    pk = node.get("pk", "?")
    error = node.get("error")
    if error:
        return f"- PK {pk}: unavailable ({error})"

    details = [
        f"PK {pk}",
        f"type={node.get('node_type') or node.get('type') or 'Unknown'}",
        f"label={node.get('label') or 'N/A'}",
    ]
    if node.get("formula"):
        details.append(f"formula={node['formula']}")
    if node.get("process_state"):
        details.append(f"process_state={node['process_state']}")
    if node.get("ctime"):
        details.append(f"ctime={node['ctime']}")
    return "- " + " | ".join(details)


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


def _build_validation_summary(validation: dict[str, Any]) -> dict[str, Any]:
    errors = _extract_messages(
        validation,
        ("error", "errors", "validation_errors", "blocking_errors", "missing_inputs", "missing"),
    )
    warnings = _extract_messages(
        validation,
        ("warnings", "validation_warnings", "non_blocking_warnings"),
    )
    notes = _extract_messages(validation, ("notes", "messages", "summary"))

    status_raw = validation.get("status")
    status = str(status_raw).strip() if status_raw is not None else ""
    status_upper = status.upper()
    is_valid_field = validation.get("is_valid")
    if isinstance(is_valid_field, bool):
        is_valid = is_valid_field
    elif status_upper in {"VALID", "VALIDATION_OK", "OK", "SUCCESS", "PASSED"}:
        is_valid = True
    elif status_upper in {"INVALID", "VALIDATION_FAILED", "FAILED", "ERROR"}:
        is_valid = False
    else:
        is_valid = not errors

    normalized_status = status or ("VALIDATION_OK" if is_valid else "VALIDATION_FAILED")
    summary_lines = [
        f"Status: {normalized_status}",
        f"Valid: {'yes' if is_valid else 'no'}",
        f"Blocking errors: {len(errors)}",
        f"Warnings: {len(warnings)}",
    ]
    if errors:
        summary_lines.append(f"Top error: {errors[0]}")
    if warnings:
        summary_lines.append(f"Top warning: {warnings[0]}")
    if notes and not errors and not warnings:
        summary_lines.append(f"Note: {notes[0]}")

    return {
        "status": normalized_status,
        "is_valid": is_valid,
        "blocking_error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
        "summary_text": "\n".join(summary_lines),
    }


def _flatten_text_payload(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        pieces: list[str] = []
        for key, value in payload.items():
            pieces.append(str(key))
            nested = _flatten_text_payload(value)
            if nested:
                pieces.append(nested)
        return " ".join(pieces)
    if isinstance(payload, (list, tuple, set)):
        return " ".join(_flatten_text_payload(item) for item in payload)
    return str(payload)


def _looks_like_missing_pseudopotential_error(payload: Any) -> bool:
    text = _flatten_text_payload(payload).strip().lower()
    if not text:
        return False
    if "pseudo" not in text and "pseudopotential" not in text:
        return False
    if not any(token in text for token in ("missing", "not found", "failed", "cannot", "unable", "unknown")):
        return False
    return any(token in text for token in ("sssp", "pseudo family", "pseudo_family", "pseudopotential family"))


def _build_pseudodojo_overrides() -> dict[str, Any]:
    return _build_pseudo_family_overrides("PseudoDojo")


def _build_pseudo_family_overrides(pseudo_family_label: str) -> dict[str, Any]:
    value = str(pseudo_family_label or "").strip() or "PseudoDojo"
    return {
        "pseudo_family": value,
        "pseudo_family_label": value,
        "pseudopotential_family": value,
        "pseudo_family_name": value,
    }


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


def _extract_group_labels(payload: Any) -> list[str]:
    if isinstance(payload, str):
        return []
    if isinstance(payload, dict):
        candidates = payload.get("items")
        if isinstance(candidates, list):
            payload = candidates
        else:
            payload = [payload]
    if not isinstance(payload, list):
        return []

    labels: list[str] = []
    seen: set[str] = set()
    for item in payload:
        if isinstance(item, str):
            label = item.strip()
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "").strip()
        else:
            label = ""
        lowered = label.lower()
        if not label or lowered in seen:
            continue
        seen.add(lowered)
        labels.append(label)
    return labels


def _select_best_pseudo_family_label(labels: list[str]) -> str | None:
    if not labels:
        return None

    def _score(label: str) -> tuple[int, int, int]:
        text = label.lower()
        score = 0
        if "pseudodojo" in text:
            score += 50
        elif "sssp" in text:
            score += 30
        elif "sg15" in text:
            score += 20
        if "pbe" in text:
            score += 6
        if "standard" in text:
            score += 4
        if "efficiency" in text:
            score += 3
        return (score, -len(text), text.count("/"))

    ranked = sorted(labels, key=_score, reverse=True)
    return ranked[0]


async def _resolve_worker_pseudo_family_label() -> str | None:
    discovered: list[str] = []
    for keyword in ("PseudoDojo", "SSSP", "SG15"):
        payload = await list_group_labels(keyword)
        discovered.extend(_extract_group_labels(payload))

    deduped: list[str] = []
    seen: set[str] = set()
    for label in discovered:
        lowered = label.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(label)
    return _select_best_pseudo_family_label(deduped)


def _find_first_named_value(payload: Any, candidate_keys: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).strip().lower()
            if lowered in candidate_keys and value not in (None, "", [], {}):
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


def _extract_submission_inputs(draft: dict[str, Any]) -> dict[str, Any]:
    for key in ("inputs", "builder", "draft"):
        value = draft.get(key)
        if isinstance(value, dict):
            return value
    return draft


def _extract_process_label(draft: dict[str, Any], fallback: str | None = None) -> str:
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
    return fallback or "AiiDA Workflow"


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
                    pk = _coerce_positive_int(value)
                    if pk is not None:
                        append_entry(pk, key_path, key_text)
                elif lowered in explicit_pk_list_keys and isinstance(value, list):
                    for index, item in enumerate(value):
                        pk = _coerce_positive_int(item)
                        if pk is None:
                            continue
                        append_entry(pk, f"{key_path}[{index}]", key_text)

                if isinstance(value, (dict, list)):
                    walk(value, key_path)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                item_path = f"{path}[{index}]" if path else f"[{index}]"
                walk(item, item_path)

    walk(payload)
    return entries[:120]


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


def _build_submission_draft_payload(
    draft: dict[str, Any],
    *,
    fallback_process_label: str | None = None,
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

    process_label = _extract_process_label(draft, fallback=fallback_process_label)
    payload = {
        "process_label": process_label,
        "inputs": inputs,
        "primary_inputs": _extract_primary_inputs(inputs),
        "recommended_inputs": recommended_inputs,
        "advanced_settings": advanced_settings,
        "meta": {
            "pk_map": _collect_pk_map(inputs),
            "target_computer": _extract_target_computer(draft),
            "parallel_settings": parallel_settings,
            "workchain": process_label,
        },
    }
    return enrich_submission_draft_payload(payload)


def _format_submission_draft_tag(submission_draft: dict[str, Any]) -> str:
    return f"{SUBMISSION_DRAFT_PREFIX}\n" + json.dumps(
        submission_draft,
        ensure_ascii=True,
        indent=2,
    )


def _cache_pending_submission(
    ctx: RunContext[AiiDADeps],
    draft: dict[str, Any],
    validation: dict[str, Any],
    validation_summary: dict[str, Any],
    submission_draft: dict[str, Any] | None = None,
) -> None:
    cached_payload = {
        "draft": draft,
        "validation": validation,
        "validation_summary": validation_summary,
    }
    if isinstance(submission_draft, dict):
        cached_payload["submission_draft"] = submission_draft
    ctx.deps.set_registry_value(_PENDING_SUBMISSION_KEY, cached_payload)
    memory = getattr(ctx.deps, "memory", None)
    if memory:
        memory.set_kv(_PENDING_SUBMISSION_KEY, cached_payload)


def _get_pending_submission(ctx: RunContext[AiiDADeps]) -> dict[str, Any] | None:
    cached = ctx.deps.get_registry_value(_PENDING_SUBMISSION_KEY)
    if isinstance(cached, dict):
        return cached

    memory = getattr(ctx.deps, "memory", None)
    if memory:
        persisted = memory.get_kv(_PENDING_SUBMISSION_KEY)
        if isinstance(persisted, dict):
            ctx.deps.set_registry_value(_PENDING_SUBMISSION_KEY, persisted)
            return persisted
    return None


def _clear_pending_submission(ctx: RunContext[AiiDADeps]) -> None:
    if isinstance(ctx.deps.registry, dict):
        ctx.deps.registry.pop(_PENDING_SUBMISSION_KEY, None)

    memory = getattr(ctx.deps, "memory", None)
    if memory:
        memory.set_kv(_PENDING_SUBMISSION_KEY, None)


@aiida_researcher.system_prompt(dynamic=True)
def add_referenced_nodes_prompt(ctx: RunContext[AiiDADeps]) -> str:
    context_nodes = getattr(ctx.deps, "context_nodes", None) or []
    if not context_nodes:
        return ""

    max_items = 12
    lines = [
        REFERENCED_NODES_HEADER,
        REFERENCED_NODES_INTRO,
    ]
    for node in context_nodes[:max_items]:
        lines.append(_format_context_node_line(node))
    if len(context_nodes) > max_items:
        lines.append(
            REFERENCED_NODES_OMITTED_TEMPLATE.format(
                omitted_count=len(context_nodes) - max_items,
            )
        )
    return "\n".join(lines)


@aiida_researcher.system_prompt(dynamic=True)
def add_specialized_skills_prompt(ctx: RunContext[AiiDADeps]) -> str:  # noqa: ARG001
    if not _STARTUP_SPECIALIZED_SKILLS:
        return ""
    lines = [
        "### SPECIALIZED SKILLS",
        "Worker-side registry skills available via `call_specialized_skill`:",
    ]
    for item in _STARTUP_SPECIALIZED_SKILLS[:20]:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        description = str(item.get("description") or "").strip()
        if description:
            lines.append(f"- {name}: {description}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


@aiida_researcher.tool
async def list_profiles(ctx: RunContext[AiiDADeps]):
    """List all configured profiles known by the active worker bridge."""
    payload = await list_system_profiles()
    if isinstance(payload, str):
        return {"error": payload}

    if isinstance(payload, dict):
        profiles = payload.get("profiles")
        if isinstance(profiles, list):
            return profiles
        return payload

    return payload


@aiida_researcher.tool
async def list_archives(ctx: RunContext[AiiDADeps]):
    """List `.aiida`/`.zip` archives visible to the worker."""
    return await list_local_archives()


@aiida_researcher.tool
async def switch_aiida_profile(ctx: RunContext[AiiDADeps], profile_name: str):
    """Switch active worker profile."""
    ctx.deps.log_step(f"Switching to profile: {profile_name}")
    return await switch_profile(profile_name)


@aiida_researcher.tool
async def get_db_statistics(ctx: RunContext[AiiDADeps]):
    """Get high-level infra/database counts from worker statistics endpoint."""
    return await get_statistics()


@aiida_researcher.tool
async def get_db_summary(ctx: RunContext[AiiDADeps]):
    """Get compact database health summary."""
    return await get_database_summary()


@aiida_researcher.tool
async def get_source_map(ctx: RunContext[AiiDADeps], target: str):
    """Get unified profile/archive group map from worker."""
    return await get_unified_source_map(target)


@aiida_researcher.tool
async def list_aiida_groups(ctx: RunContext[AiiDADeps], search_string: str = None):
    """List groups, optionally filtered by substring."""
    return await list_groups(search_string)


@aiida_researcher.tool
async def inspect_aiida_group(ctx: RunContext[AiiDADeps], group_name: str, limit: int = 20):
    """Inspect one group with node attributes/extras."""
    ctx.deps.log_step(f"Analyzing group: {group_name}")
    return await inspect_group(group_name, limit)


@aiida_researcher.tool
async def inspect_node_details(ctx: RunContext[AiiDADeps], pk: int):
    """Get structured node summary by PK."""
    return await get_node_summary(pk)


@aiida_researcher.tool
async def list_remote_plugins(ctx: RunContext[AiiDADeps]):
    """Source of truth for available WorkChains from worker bridge."""
    ctx.deps.log_step("Fetching remote plugin list from worker bridge")
    return await list_remote_plugins_via_bridge()


@aiida_researcher.tool
async def inspect_lab_infrastructure(ctx: RunContext[AiiDADeps]):
    """Inspect remote infrastructure (profile/daemon/computers/codes) before submission."""
    ctx.deps.log_step("Inspecting lab infrastructure from worker bridge")
    return await inspect_lab_infrastructure_via_bridge()


@aiida_researcher.tool
async def get_remote_workchain_spec(ctx: RunContext[AiiDADeps], entry_point: str):
    """Read WorkChain spec from worker bridge."""
    ctx.deps.log_step(f"Fetching remote WorkChain spec: {entry_point}")
    return await get_remote_workchain_spec_via_bridge(entry_point)


@aiida_researcher.tool
async def inspect_process_details(ctx: RunContext[AiiDADeps], identifier: str):
    """Inspect process summary/logs/provenance by PK/UUID."""
    ctx.deps.log_step(f"Inspecting process logs: {identifier}")
    return await inspect_process(identifier)


@aiida_researcher.tool
async def get_recent_aiida_processes(ctx: RunContext[AiiDADeps], limit: int = 15):
    """Fetch recent processes for status overview."""
    return await fetch_recent_processes(limit)


@aiida_researcher.tool
async def check_workflow_spec(ctx: RunContext[AiiDADeps], entry_point: str):
    """Inspect WorkChain inputs via worker spec endpoint."""
    return await inspect_workchain_spec(entry_point)


@aiida_researcher.tool
async def submit_new_workflow(
    ctx: RunContext[AiiDADeps],
    workchain: str,
    structure_pk: int,
    code: str,
    protocol: str = "moderate",
):
    """Draft and validate a new WorkChain; do not submit until user confirmation."""
    ctx.deps.log_step(f"Preparing workflow for validation: {workchain}")
    draft = await draft_workchain_builder(workchain, structure_pk, code, protocol)
    if not (isinstance(draft, dict) and draft.get("status") == "DRAFT_READY"):
        if _looks_like_missing_pseudopotential_error(draft):
            resolved_pseudo_family = await _resolve_worker_pseudo_family_label()
            if resolved_pseudo_family:
                ctx.deps.log_step(
                    f"Protocol builder missing pseudo family; retrying with {resolved_pseudo_family}"
                )
                pseudo_overrides = _build_pseudo_family_overrides(resolved_pseudo_family)
            else:
                ctx.deps.log_step("Protocol builder missing pseudo family; retrying with PseudoDojo override")
                pseudo_overrides = _build_pseudodojo_overrides()
            draft = await draft_workchain_builder(
                workchain,
                structure_pk,
                code,
                protocol,
                overrides=pseudo_overrides,
            )
    if isinstance(draft, dict) and draft.get("status") == "DRAFT_READY":
        validation = await validate_job(draft)
        if isinstance(validation, str):
            return {
                "error": "Failed to validate workflow draft",
                "details": validation,
                "draft": draft,
            }
        if not isinstance(validation, dict):
            return {
                "error": "Validation returned an unexpected payload",
                "details": validation,
                "draft": draft,
            }
        if validation.get("error"):
            return {
                "error": "Failed to validate workflow draft",
                "details": validation,
                "draft": draft,
            }

        validation_summary = _build_validation_summary(validation)
        submission_draft = _build_submission_draft_payload(
            draft,
            fallback_process_label=workchain,
        )
        submission_draft_meta = submission_draft.get("meta")
        if isinstance(submission_draft_meta, dict):
            submission_draft_meta["validation"] = validation
            submission_draft_meta["validation_summary"] = validation_summary
            submission_draft_meta["draft"] = draft
        _cache_pending_submission(
            ctx,
            draft,
            validation,
            validation_summary,
            submission_draft=submission_draft,
        )
        return {
            "status": "SUBMISSION_DRAFT",
            "workchain": workchain,
            "submission_draft": submission_draft,
            "submission_draft_tag": _format_submission_draft_tag(submission_draft),
            "validation_summary": validation_summary,
            "validation": validation,
            "next_step": SUBMISSION_DRAFT_NEXT_STEP_GUIDANCE,
        }

    return {"error": "Failed to draft workflow", "details": draft}


@aiida_researcher.tool
async def submit_validated_workflow(ctx: RunContext[AiiDADeps]):
    """Submit the latest validated workflow only after explicit user confirmation."""
    pending = _get_pending_submission(ctx)
    if not isinstance(pending, dict):
        return {
            "error": "No validated workflow is pending submission. Run submit_new_workflow first."
        }

    draft = pending.get("draft")
    validation_summary = pending.get("validation_summary")
    if not isinstance(draft, dict):
        return {
            "error": "Pending draft is unavailable. Please run submit_new_workflow again."
        }
    if isinstance(validation_summary, dict) and not validation_summary.get("is_valid", False):
        return {
            "error": "Validation contains blocking issues; submission aborted.",
            "validation_summary": validation_summary,
        }

    ctx.deps.log_step("Submitting workflow after explicit user confirmation")
    submission = await submit_job(draft)
    if isinstance(submission, str):
        return {
            "error": "Workflow submission failed",
            "details": submission,
        }
    if isinstance(submission, dict) and submission.get("error"):
        return {
            "error": "Workflow submission failed",
            "details": submission,
        }

    _clear_pending_submission(ctx)
    return {
        "status": "SUBMITTED",
        "submission": submission,
        "validation_summary": validation_summary,
    }


@aiida_researcher.tool
async def get_bands_data(ctx: RunContext[AiiDADeps], pk: int):
    """Retrieve plot-ready bands payload by node PK."""
    return await get_bands_plot_data(pk)


@aiida_researcher.tool
async def list_remote_path_files(ctx: RunContext[AiiDADeps], remote_path_pk: int):
    """List files in a RemoteData directory."""
    return await list_remote_files(remote_path_pk)


@aiida_researcher.tool
async def get_remote_file(ctx: RunContext[AiiDADeps], remote_path_pk: int, filename: str):
    """Read file content from RemoteData."""
    return await get_remote_file_content(remote_path_pk, filename)


@aiida_researcher.tool
async def get_node_file(ctx: RunContext[AiiDADeps], pk: int, filename: str):
    """Read file content from node repository/folder data."""
    return await get_node_file_content(pk, filename)


@aiida_researcher.tool
async def call_specialized_skill(
    ctx: RunContext[AiiDADeps],
    skill_name: str,
    args: dict[str, Any] | None = None,
):
    """Execute one worker-registered specialized skill by name."""
    ctx.deps.log_step(f"Running specialized skill: {skill_name}")
    return await execute_specialized_skill(skill_name, args=args or {})


@aiida_researcher.tool
async def persist_current_script(
    ctx: RunContext[AiiDADeps],
    name: str,
    script: str,
    description: str | None = None,
    overwrite: bool = True,
):
    """Persist a successful script into worker registry for future skill reuse."""
    ctx.deps.log_step(f"Persisting specialized skill: {name}")
    return await register_specialized_skill(
        skill_name=name,
        script=script,
        description=description,
        overwrite=overwrite,
    )


@aiida_researcher.tool
async def run_aiida_code_script(
    ctx: RunContext[AiiDADeps],
    script: str,
    intent: str | None = None,
    nodes_involved: list[int] | None = None,
):
    """Execute targeted Python/AiiDA code on the worker."""
    ctx.deps.log_step("Running custom research script on worker")
    result = await run_python_code(
        script,
        intent=intent,
        nodes_involved=nodes_involved,
    )
    if isinstance(result, dict):
        missing_module = result.get("missing_module")
        if isinstance(missing_module, str) and missing_module.strip():
            ctx.deps.log_step(f"Custom script missing module: {missing_module}")
            if missing_module.startswith("aiida_pseudo"):
                result["recovery_suggestion"] = (
                    "aiida_pseudo import is unavailable on worker. "
                    "Use submit_new_workflow with pseudo override, or inspect pseudo families via bridge/group labels "
                    "without importing aiida_pseudo modules."
                )
    return result
