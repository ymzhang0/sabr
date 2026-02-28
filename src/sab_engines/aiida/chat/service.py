from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from typing import Any, Callable

from loguru import logger

from src.sab_core.logging_utils import log_event


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
        payload.append(
            {
                "role": str(message.get("role", "assistant")),
                "text": str(message.get("text", "")),
                "status": str(message.get("status", "done")),
                "turn_id": int(message.get("turn_id") or 0),
            }
        )
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


def _update_assistant_message(state: Any, turn_id: int, text: str, status: str = "thinking") -> None:
    chat_history = get_chat_history(state)
    for msg in reversed(chat_history):
        if msg.get("role") == "assistant" and msg.get("turn_id") == turn_id:
            msg["text"] = text
            msg["status"] = status
            touch_chat(state)
            return
    logger.warning(log_event("aiida.chat_turn.message_update_missed", turn_id=turn_id, status=status))


def _append_assistant_message(state: Any, turn_id: int, text: str, status: str = "done") -> None:
    chat_history = get_chat_history(state)
    chat_history.append(
        {
            "role": "assistant",
            "text": text,
            "status": status,
            "turn_id": turn_id,
        }
    )
    touch_chat(state)
    logger.info(
        log_event(
            "aiida.chat_turn.message_append",
            turn_id=turn_id,
            status=status,
            chars=len(text),
        )
    )


def _to_agent_model_name(name: str) -> str:
    if ":" in name:
        return name
    return f"google-gla:{name}"


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


async def _thinking_status_ticker(state: Any, turn_id: int, stop_event: asyncio.Event) -> None:
    started = time.perf_counter()
    dots = 0
    while not stop_event.is_set():
        elapsed = int(time.perf_counter() - started)
        dots = (dots % 3) + 1
        _update_assistant_message(
            state,
            turn_id,
            f"Thinking: waiting for Gemini response ({elapsed}s){'.' * dots}",
            status="thinking",
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

    chat_history.append({"role": "user", "text": user_intent, "turn_id": turn_id})
    chat_history.append(
        {
            "role": "assistant",
            "text": "Thinking: request queued.",
            "status": "thinking",
            "turn_id": turn_id,
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

            spinner_task = asyncio.create_task(
                _thinking_status_ticker(state=state, turn_id=turn_id, stop_event=spinner_stop)
            )
            run_intent = _inject_context_priority_instruction(user_intent, normalized_node_ids)
            result = await agent.run(
                run_intent,
                deps=current_deps,
                model=_to_agent_model_name(selected_model),
            )

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
            _append_assistant_message(state, turn_id, answer_text, status="done")
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
