# engines/aiida/api.py
import asyncio
import hashlib
import json
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import tkinter as tk
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastui import FastUI
from fastui import components as c
from fastui import events as e
from google import genai
from loguru import logger
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from tkinter import filedialog

from src.sab_core.config import settings
from src.sab_core.logging_utils import get_log_buffer_snapshot, log_event

from .hub import hub
from .tools import get_recent_nodes, get_recent_processes, list_group_labels
from .ui import fastui as ui
from .ui.legacy_fastui.fastui import get_aiida_dashboard_layout, get_chat_interface

def ask_for_folder_path():
    """
    Open a native file-selection dialog on the server host machine.
    """
    logger.info(log_event("aiida.archive_picker.open"))
    root = tk.Tk()
    root.withdraw()  # Hide the root window.
    root.attributes('-topmost', True)  # Keep the dialog on top.
    
    # Open a file picker for archive files.
    file_selected = filedialog.askopenfilename(
        title="Select AiiDA Archive",
        filetypes=[("AiiDA Archive", "*.aiida"), ("Zip Archive", "*.zip"), ("All Files", "*.*")]
    )
    
    root.destroy()  # Close tkinter.
    
    if file_selected:
        logger.success(log_event("aiida.archive_picker.selected", path=file_selected))
        return file_selected
    else:
        logger.info(log_event("aiida.archive_picker.cancelled"))
        return None


router = APIRouter()
DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
QUICK_PROMPTS: list[tuple[str, str]] = [
    ("Check Profile", "check the current profile"),
    ("List Groups", "list all groups in current profile"),
    ("DB Summary", "show database summary"),
]
ARCHIVE_EXTENSIONS = {".aiida", ".zip"}


class FrontendChatRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=12000)
    model_name: str | None = None
    context_archive: str | None = None
    context_node_ids: list[int] | None = None


class FrontendStopChatRequest(BaseModel):
    turn_id: int | None = None


class FrontendSwitchProfileRequest(BaseModel):
    profile_name: str = Field(..., min_length=1)


def _normalize_process_state(state: str | None) -> str:
    return str(state or "unknown").strip().lower()


def _state_to_status_color(state: str | None) -> str:
    normalized = _normalize_process_state(state)
    if normalized in {"running", "created", "waiting"}:
        return "running"
    if normalized in {"finished", "completed"}:
        return "success"
    if normalized in {"failed", "excepted", "killed"}:
        return "error"
    return "idle"


def _serialize_profiles(profiles_display: list[tuple[str, str, bool]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name, display_name, is_active in profiles_display:
        items.append(
            {
                "name": str(name),
                "display_name": str(display_name),
                "is_active": bool(is_active),
                "type": "imported" if str(display_name).endswith("(imported)") else "configured",
            }
        )
    return items


def _serialize_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for process in processes:
        process_state_raw = process.get("process_state")
        state = str(process_state_raw or process.get("state") or "unknown")
        try:
            pk = int(process.get("pk", 0))
        except (TypeError, ValueError):
            pk = 0
        formula = process.get("formula")
        payload.append(
            {
                "pk": pk,
                "label": str(process.get("label") or "Unknown Task"),
                "state": state,
                "status_color": _state_to_status_color(state),
                "node_type": str(process.get("node_type") or "Node"),
                "process_state": str(process_state_raw) if process_state_raw is not None else None,
                "formula": str(formula) if formula else None,
            }
        )
    return payload


def _serialize_chat_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _normalize_context_node_ids(raw: Any) -> list[int]:
    if raw is None:
        return []

    values: list[Any]
    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return []

        values = []
        with suppress(json.JSONDecodeError):
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                values = parsed
            else:
                values = [parsed]
        if not values:
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


def _get_structure_formula(node: Any) -> str | None:
    for method_name in ("get_formula", "get_chemical_formula"):
        method = getattr(node, method_name, None)
        if not callable(method):
            continue
        try:
            formula = method()
        except TypeError:
            formula = method(mode="hill")
        except Exception:
            continue
        if formula:
            return str(formula)
    return None


def _fetch_context_nodes(context_node_ids: list[int]) -> list[dict[str, Any]]:
    if not context_node_ids:
        return []

    if not hub.current_profile:
        hub.start()

    from aiida import orm

    context_nodes: list[dict[str, Any]] = []
    for pk in context_node_ids:
        try:
            node = orm.load_node(pk)
        except Exception as err:
            context_nodes.append({"pk": pk, "error": str(err)})
            continue

        process_state_value: str | None = None
        if isinstance(node, orm.ProcessNode):
            process_state = getattr(node, "process_state", None)
            process_state_value = (
                process_state.value if hasattr(process_state, "value")
                else (str(process_state) if process_state else None)
            )

        context_nodes.append(
            {
                "pk": int(node.pk),
                "uuid": str(getattr(node, "uuid", "")),
                "label": str(
                    getattr(node, "label", None)
                    or getattr(node, "process_label", None)
                    or node.__class__.__name__
                ),
                "node_type": str(node.__class__.__name__),
                "process_state": process_state_value,
                "formula": _get_structure_formula(node) if isinstance(node, orm.StructureData) else None,
                "ctime": (
                    node.ctime.strftime("%Y-%m-%d %H:%M:%S")
                    if getattr(node, "ctime", None) is not None
                    else None
                ),
            }
        )
    return context_nodes


def _sanitize_upload_name(filename: str) -> str:
    safe = Path(filename).name.replace(" ", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch in {"-", "_", "."}) or "archive.aiida"


def _get_sidebar_state() -> tuple[list, list]:
    """Load sidebar context for all dashboard-like pages."""
    if not hub.current_profile:
        hub.start()
    try:
        recent_procs = get_recent_processes(limit=5)
    except Exception as e:
        logger.error(log_event("aiida.processes.fetch.failed", error=str(e)))
        recent_procs = []
    return hub.get_display_list(), recent_procs


def _get_frontend_group_labels() -> list[str]:
    if not hub.current_profile:
        hub.start()
    return list_group_labels()


def _get_frontend_nodes(
    limit: int = 15,
    group_label: str | None = None,
    node_type: str | None = None,
) -> list[dict[str, Any]]:
    if not hub.current_profile:
        hub.start()
    return get_recent_nodes(limit=limit, group_label=group_label, node_type=node_type)


def _get_chat_history(state) -> list[dict[str, str]]:
    """Keep an in-memory chat transcript for FastUI rendering."""
    history = getattr(state, "chat_history", None)
    if history is None:
        history = []
        state.chat_history = history
    if not hasattr(state, "chat_version"):
        state.chat_version = 0
    return history


def _touch_chat(state) -> None:
    state.chat_version = getattr(state, "chat_version", 0) + 1


def _normalize_model_name(name: str) -> str:
    if name.startswith("models/"):
        return name.split("/", 1)[1]
    return name


def _to_agent_model_name(name: str) -> str:
    if ":" in name:
        return name
    return f"google-gla:{name}"


def _fetch_genai_models() -> list[str]:
    """Query Gemini model list and keep only generation-capable Gemini models."""
    api_key = settings.GEMINI_API_KEY
    if api_key == "your-key-here":
        api_key = None

    client = genai.Client(api_key=api_key)
    discovered: list[str] = []
    for model in client.models.list():
        model_name = _normalize_model_name(getattr(model, "name", "") or "")
        if not model_name.startswith("gemini"):
            continue

        supported_actions = getattr(model, "supported_actions", None) or []
        if supported_actions and "generateContent" not in supported_actions:
            continue

        discovered.append(model_name)

    # Keep order stable while removing duplicates.
    deduped = list(dict.fromkeys(discovered))
    return deduped


def _get_available_models(state) -> list[str]:
    cached = getattr(state, "available_models", None)
    cached_at = getattr(state, "available_models_cached_at", 0.0)
    now = time.time()

    # Cache model list for 15 minutes.
    if cached and (now - cached_at) < 900:
        return cached

    try:
        models = _fetch_genai_models()
        if not models:
            models = DEFAULT_MODELS
    except Exception as e:
        logger.warning(log_event("aiida.models.fetch.fallback", error=str(e)))
        models = DEFAULT_MODELS

    state.available_models = models
    state.available_models_cached_at = now
    return models


def _get_selected_model(state, available_models: list[str]) -> str:
    selected = getattr(state, "selected_model", None)
    if selected in available_models:
        return selected
    fallback = available_models[0]
    state.selected_model = fallback
    return fallback


def _get_quick_shortcuts() -> list[dict[str, str]]:
    return [
        {"label": label, "url": f"/aiida/chat/quick/{idx}"}
        for idx, (label, _prompt) in enumerate(QUICK_PROMPTS)
    ]


def _render_chat_page(state) -> FastUI:
    profiles_display, recent_procs = _get_sidebar_state()
    available_models = _get_available_models(state)
    selected_model = _get_selected_model(state, available_models)
    _version, log_lines = get_log_buffer_snapshot(limit=240)
    return get_aiida_dashboard_layout(
        content=get_chat_interface(
            chat_history=_get_chat_history(state),
            model_name=selected_model,
            available_models=available_models,
            quick_shortcuts=_get_quick_shortcuts(),
        ),
        profiles_display=profiles_display,
        processes=recent_procs,
        log_lines=log_lines,
    )


def _ensure_chat_lock(state) -> asyncio.Lock:
    lock = getattr(state, "chat_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        state.chat_lock = lock
    return lock


def _ensure_chat_task_registry(state) -> dict[int, asyncio.Task]:
    tasks = getattr(state, "chat_turn_tasks", None)
    if tasks is None:
        tasks = {}
        state.chat_turn_tasks = tasks
    return tasks


def _update_assistant_message(state, turn_id: int, text: str, status: str = "thinking") -> None:
    chat_history = _get_chat_history(state)
    for msg in reversed(chat_history):
        if msg.get("role") == "assistant" and msg.get("turn_id") == turn_id:
            msg["text"] = text
            msg["status"] = status
            _touch_chat(state)
            return
    logger.warning(log_event("aiida.chat_turn.message_update_missed", turn_id=turn_id, status=status))


def _append_assistant_message(state, turn_id: int, text: str, status: str = "done") -> None:
    chat_history = _get_chat_history(state)
    chat_history.append(
        {
            "role": "assistant",
            "text": text,
            "status": status,
            "turn_id": turn_id,
        }
    )
    _touch_chat(state)
    logger.info(
        log_event(
            "aiida.chat_turn.message_append",
            turn_id=turn_id,
            status=status,
            chars=len(text),
        )
    )


async def _thinking_status_ticker(state, turn_id: int, stop_event: asyncio.Event) -> None:
    """Update waiting status periodically so frontend can render live thinking changes."""
    started = time.perf_counter()
    dots = 0
    while not stop_event.is_set():
        elapsed = int(time.perf_counter() - started)
        dots = (dots % 3) + 1
        _update_assistant_message(
            state,
            turn_id,
            f"Thinking: 正在调用 Gemini 并等待响应 ({elapsed}s){'.' * dots}",
            status="thinking",
        )
        await asyncio.sleep(0.9)


def _cancel_chat_turn(state, turn_id: int | None = None) -> int | None:
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


def _start_chat_turn(
    state,
    user_intent: str,
    selected_model: str,
    context_archive: str | None = None,
    context_node_ids: list[int] | None = None,
    source: str = "form",
) -> int:
    chat_history = _get_chat_history(state)
    normalized_node_ids = _normalize_context_node_ids(context_node_ids)
    turn_id = getattr(state, "chat_turn_seq", 0) + 1
    state.chat_turn_seq = turn_id
    chat_history.append({"role": "user", "text": user_intent, "turn_id": turn_id})
    chat_history.append({
        "role": "assistant",
        "text": "Thinking: 已接收到问题，正在准备上下文...",
        "status": "thinking",
        "turn_id": turn_id,
    })
    _touch_chat(state)
    logger.info(
        log_event(
            "aiida.chat_turn.queued",
            turn_id=turn_id,
            source=source,
            model=selected_model,
            intent=user_intent[:120],
            context=context_archive,
            context_node_ids=",".join(str(pk) for pk in normalized_node_ids) or None,
        )
    )
    logger.debug(
        log_event(
            "aiida.chat_turn.queued_history",
            turn_id=turn_id,
            digest=_history_digest(chat_history),
        )
    )
    task = asyncio.create_task(
        _execute_chat_turn(
            state=state,
            turn_id=turn_id,
            user_intent=user_intent,
            selected_model=selected_model,
            context_archive=context_archive,
            context_node_ids=normalized_node_ids,
        )
    )
    _ensure_chat_task_registry(state)[turn_id] = task
    task.add_done_callback(
        lambda _task, _state=state, _turn_id=turn_id: _ensure_chat_task_registry(_state).pop(_turn_id, None)
    )
    return turn_id


async def _execute_chat_turn(
    state,
    turn_id: int,
    user_intent: str,
    selected_model: str,
    context_archive: str | None = None,
    context_node_ids: list[int] | None = None,
) -> None:
    """Run one chat turn asynchronously and update the assistant placeholder."""
    agent = getattr(state, "agent", None)
    DepsClass = getattr(state, "deps_class", None)
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
                context_node_ids=",".join(str(pk) for pk in _normalize_context_node_ids(context_node_ids)) or None,
            )
        )

        try:
            _update_assistant_message(
                state, turn_id, "Thinking: 正在初始化 AiiDA 依赖...", status="thinking"
            )
            normalized_node_ids = _normalize_context_node_ids(context_node_ids)
            context_nodes = _fetch_context_nodes(normalized_node_ids)
            if context_nodes:
                _update_assistant_message(
                    state,
                    turn_id,
                    f"Thinking: 已加载 {len(context_nodes)} 个参考节点，正在准备上下文...",
                    status="thinking",
                )
            deps_kwargs: dict[str, Any] = {
                "archive_path": context_archive,
                "memory": getattr(state, "memory", None),
            }
            if "context_nodes" in getattr(DepsClass, "__annotations__", {}):
                deps_kwargs["context_nodes"] = context_nodes
            current_deps = DepsClass(
                **deps_kwargs
            )

            _update_assistant_message(
                state, turn_id, "Thinking: 正在调用 Gemini 并等待响应...", status="thinking"
            )
            spinner_task = asyncio.create_task(
                _thinking_status_ticker(state=state, turn_id=turn_id, stop_event=spinner_stop)
            )
            result = await agent.run(
                user_intent,
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

            # pydantic-ai v1 uses `result.output`; keep backward compatibility.
            output = getattr(result, "output", None)
            if output is None:
                output = getattr(result, "data", None)

            if output is None:
                raise RuntimeError("Agent returned no output payload")

            if hasattr(current_deps, "step_history") and hasattr(output, "thought_process"):
                output.thought_process = current_deps.step_history

            if hasattr(output, "answer"):
                answer_text = str(output.answer)
            else:
                answer_text = str(output)

            _append_assistant_message(state, turn_id, answer_text, status="done")
            state.chat_history = _get_chat_history(state)[-200:]
            _touch_chat(state)
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
                    state.memory.add_turn(
                        intent=user_intent,
                        response=answer_text,
                        metadata={
                            "context_archive": context_archive,
                            "context_node_ids": normalized_node_ids,
                        },
                    )
                except Exception as mem_e:
                    logger.warning(
                        log_event(
                            "aiida.chat_turn.persist_failed",
                            turn_id=turn_id,
                            error=str(mem_e),
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
            state.chat_history = _get_chat_history(state)[-200:]
            _touch_chat(state)
            logger.info(
                log_event(
                    "aiida.chat_turn.cancelled",
                    turn_id=turn_id,
                    elapsed=f"{elapsed:.2f}s",
                    model=selected_model,
                )
            )
            raise
        except Exception as err:
            elapsed = time.perf_counter() - t0
            logger.exception(
                log_event(
                    "aiida.chat_turn.failed",
                    turn_id=turn_id,
                    elapsed=f"{elapsed:.2f}s",
                    model=selected_model,
                    error=str(err),
                )
            )
            _append_assistant_message(
                state, turn_id, f"处理请求时出现错误：{str(err)}", status="error"
            )
            state.chat_history = _get_chat_history(state)[-200:]
            _touch_chat(state)
        finally:
            spinner_stop.set()
            if spinner_task:
                spinner_task.cancel()
                with suppress(asyncio.CancelledError):
                    await spinner_task


def _first_value(value: Any) -> Any:
    """Normalize possible list-like form payloads to a scalar."""
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _debounce_request(state, key: str, window_seconds: float = 0.5) -> bool:
    """Return True when the same action fires too frequently."""
    now = time.monotonic()
    cache = getattr(state, "request_debounce_cache", None)
    if cache is None:
        cache = {}
        state.request_debounce_cache = cache
    last_ts = float(cache.get(key, 0.0))
    cache[key] = now
    return (now - last_ts) < window_seconds


def _history_digest(history: list[dict[str, Any]], tail: int = 6) -> str:
    if not history:
        return "empty"
    chunks: list[str] = []
    for msg in history[-tail:]:
        turn = msg.get("turn_id", "-")
        role = msg.get("role", "?")
        status = msg.get("status", "-")
        text_len = len(str(msg.get("text", "")))
        chunks.append(f"{turn}:{role}/{status}:{text_len}")
    return " | ".join(chunks)


def _history_layout_debug(history: list[dict[str, Any]]) -> str:
    layout: list[str] = []
    ai_count = 0
    user_count = 0
    for msg in history:
        role = str(msg.get("role", "")).strip().lower()
        status = str(msg.get("status", "")).strip().lower()
        is_assistant = role in {"assistant", "ai", "model"} or status in {"thinking", "done", "error"}
        if is_assistant:
            ai_count += 1
            layout.append("A")
        else:
            user_count += 1
            layout.append("U")
    return f"ua={''.join(layout[-24:]) or '-'} | users={user_count} | ai={ai_count}"


def _history_ui_group_debug(history: list[dict[str, Any]]) -> str:
    grouped: list[dict[str, Any]] = []
    for msg in history:
        role = str(msg.get("role", "")).strip().lower()
        status = str(msg.get("status", "")).strip().lower()
        text = str(msg.get("text", ""))
        turn_id = msg.get("turn_id")
        is_assistant = role in {"assistant", "ai", "model"} or status in {"thinking", "done", "error"}
        if not is_assistant:
            grouped.append({"kind": "U", "turn_id": turn_id, "text_len": len(text)})
            continue
        if status == "thinking":
            grouped.append({"kind": "A", "turn_id": turn_id, "thinking": 1, "answer": 0})
            continue
        target = None
        if turn_id is not None:
            for item in reversed(grouped):
                if item.get("kind") == "A" and item.get("turn_id") == turn_id and item.get("answer", 0) == 0:
                    target = item
                    break
        if target is None:
            target = {"kind": "A", "turn_id": turn_id, "thinking": 0, "answer": 0}
            grouped.append(target)
        target["answer"] = 1
        target["answer_status"] = status or "done"

    tail = grouped[-8:]
    parts: list[str] = []
    for item in tail:
        if item["kind"] == "U":
            parts.append(f"U({item.get('turn_id', '-')})")
        else:
            parts.append(
                f"A({item.get('turn_id', '-')}:t{item.get('thinking', 0)}"
                f"a{item.get('answer', 0)}:{item.get('answer_status', '-')})"
            )
    return f"ui={','.join(parts) or '-'} | groups={len(grouped)}"


def _profiles_digest(profiles_display: list[tuple[str, str, bool]]) -> str:
    if not profiles_display:
        return "empty"
    raw = "|".join(f"{name}:{display}:{int(active)}" for name, display, active in profiles_display)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


async def _parse_chat_payload(request: Request) -> tuple[str, str | None, str | None, list[int]]:
    """
    Parse FastUI form payload safely to avoid 422 caused by strict model parsing.
    Returns (intent, model_name, context_archive, context_node_ids).
    """
    raw: dict[str, Any] = {}
    content_type = (request.headers.get("content-type") or "").lower()
    try:
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                raw = body
        else:
            form = await request.form()
            raw = dict(form)
    except Exception as e:
        logger.warning(log_event("aiida.chat_payload.parse_failed", error=str(e)))

    intent = str(_first_value(raw.get("intent")) or "").strip()
    model_name = _first_value(raw.get("model_name"))
    context_archive = _first_value(raw.get("context_archive"))
    context_node_ids = _normalize_context_node_ids(raw.get("context_node_ids"))
    logger.debug(
        log_event(
            "aiida.chat_payload.parsed",
            keys=",".join(sorted(str(k) for k in raw.keys())),
            intent_len=len(intent),
            model=model_name,
            context=context_archive,
            context_node_ids=",".join(str(pk) for pk in context_node_ids) or None,
        )
    )
    return (
        intent,
        (str(model_name) if model_name else None),
        (str(context_archive) if context_archive else None),
        context_node_ids,
    )


@router.get("/profiles/stream")
@router.get("/profiles/stream/")
async def stream_profiles(request: Request):
    """SSE endpoint for profile/archive list updates."""

    async def event_generator():
        stream_id = id(request)
        last_digest = ""
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.profile_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.profile_stream.disconnected", stream_id=stream_id))
                break
            try:
                profiles_display, _ = _get_sidebar_state()
                digest = _profiles_digest(profiles_display)
                now = time.monotonic()
                should_push = (digest != last_digest) or ((now - heartbeat_ts) >= 15)
                if should_push:
                    yield {"data": FastUI(root=ui.get_profile_panel(profiles_display)).model_dump_json()}
                    last_digest = digest
                    heartbeat_ts = now
                    logger.debug(
                        log_event(
                            "aiida.profile_stream.push",
                            stream_id=stream_id,
                            profiles=len(profiles_display),
                        )
                    )
            except Exception as err:
                logger.exception(
                    log_event("aiida.profile_stream.failed", stream_id=stream_id, error=str(err))
                )
                yield {
                    "data": FastUI(
                        root=[c.Div(class_name="text-muted small", components=[c.Text(text="Profile stream unavailable.")])]
                    ).model_dump_json()
                }
            await asyncio.sleep(0.75)

    return EventSourceResponse(event_generator())


@router.get("/processes/stream")
@router.get("/processes/stream/")
async def stream_processes(request: Request):
    """
    SSE endpoint that pushes latest process status every 3 seconds.
    """
    async def event_generator():
        stream_id = id(request)
        logger.info(log_event("aiida.process_stream.connected", stream_id=stream_id))
        if not hub.current_profile:
            hub.start()
        while True:
            # Stop the stream when the client disconnects.
            if await request.is_disconnected():
                logger.info(log_event("aiida.process_stream.disconnected", stream_id=stream_id))
                break

            # 1. Fetch latest process data.
            try:
                # Ensure this query path stays fast enough for polling.
                processes = get_recent_processes()
                
                # 2. Build and push only the process panel components.
                body = ui.get_process_panel(processes)
                
                # 3. Wrap payload in FastUI JSON.
                yield {
                    "data": FastUI(root=body).model_dump_json()
                }
            except Exception as e:
                logger.exception(
                    log_event("aiida.process_stream.failed", stream_id=stream_id, error=str(e))
                )
                yield {
                    "data": FastUI(
                        root=[
                            c.Div(
                                class_name="text-muted small px-2 py-3",
                                components=[c.Text(text="Recent processes unavailable.")]
                            )
                        ]
                    ).model_dump_json()
                }

            # 4. Throttle update frequency.
            await asyncio.sleep(3)

    return EventSourceResponse(event_generator())


@router.get("/processes")
@router.get("/processes/")
async def list_processes(
    limit: int = Query(default=15, ge=1, le=100),
    group_label: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
):
    try:
        nodes = _get_frontend_nodes(limit=limit, group_label=group_label, node_type=node_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        logger.exception(log_event("aiida.processes.list.failed", error=str(err)))
        nodes = []
    return {"items": _serialize_processes(nodes)}


@router.get("/chat/messages/stream")
@router.get("/chat/messages/stream/")
async def stream_chat_messages(request: Request):
    """
    SSE endpoint to live-update chat messages (including thinking states).
    """
    state = request.app.state

    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.chat_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.chat_stream.disconnected", stream_id=stream_id))
                break
            try:
                history = _get_chat_history(state)
                version = getattr(state, "chat_version", 0)
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 15)

                if should_push:
                    body = ui.get_chat_messages_panel(history)
                    yield {"data": FastUI(root=body).model_dump_json()}
                    logger.debug(
                        log_event(
                            "aiida.chat_stream.push",
                            stream_id=stream_id,
                            version=version,
                            messages=len(history),
                        )
                    )
                    last_version = version
                    heartbeat_ts = now
            except Exception as err:
                logger.exception(
                    log_event("aiida.chat_stream.failed", stream_id=stream_id, error=str(err))
                )
                yield {
                    "data": FastUI(
                        root=[c.Div(class_name="text-muted small", components=[c.Text(text="Chat stream unavailable.")])]
                    ).model_dump_json()
                }
            await asyncio.sleep(0.25)

    return EventSourceResponse(event_generator())


@router.get("/logs/stream")
@router.get("/logs/stream/")
async def stream_logs(request: Request):
    """SSE endpoint to stream recent backend logs into sidebar console."""

    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.log_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.log_stream.disconnected", stream_id=stream_id))
                break
            try:
                version, lines = get_log_buffer_snapshot(limit=240)
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 2.0)
                if should_push:
                    yield {"data": FastUI(root=ui.get_log_panel(lines)).model_dump_json()}
                    last_version = version
                    heartbeat_ts = now
            except Exception as err:
                logger.exception(
                    log_event("aiida.log_stream.failed", stream_id=stream_id, error=str(err))
                )
                yield {
                    "data": FastUI(
                        root=[c.Div(class_name="text-muted small", components=[c.Text(text="Log stream unavailable.")])]
                    ).model_dump_json()
                }
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@router.get("/frontend/bootstrap")
async def frontend_bootstrap(request: Request):
    """Initial payload for the React dashboard."""
    state = request.app.state
    profiles_display, _recent_processes = _get_sidebar_state()
    try:
        processes = _get_frontend_nodes(limit=15)
    except Exception as err:
        logger.exception(log_event("aiida.frontend.bootstrap.processes.failed", error=str(err)))
        processes = []
    try:
        groups = _get_frontend_group_labels()
    except Exception as err:
        logger.exception(log_event("aiida.frontend.bootstrap.groups.failed", error=str(err)))
        groups = []
    available_models = _get_available_models(state)
    selected_model = _get_selected_model(state, available_models)
    log_version, log_lines = get_log_buffer_snapshot(limit=240)
    chat_history = _serialize_chat_history(_get_chat_history(state))

    return {
        "profiles": _serialize_profiles(profiles_display),
        "current_profile": hub.current_profile,
        "processes": _serialize_processes(processes),
        "groups": groups,
        "chat": {
            "messages": chat_history,
            "version": int(getattr(state, "chat_version", 0)),
        },
        "logs": {
            "version": log_version,
            "lines": log_lines[-160:],
        },
        "models": available_models,
        "selected_model": selected_model,
        "quick_prompts": [{"label": label, "prompt": prompt} for label, prompt in QUICK_PROMPTS],
    }


@router.get("/frontend/profiles")
async def frontend_profiles():
    profiles_display, _ = _get_sidebar_state()
    return {
        "current_profile": hub.current_profile,
        "profiles": _serialize_profiles(profiles_display),
    }


@router.get("/frontend/groups")
async def frontend_groups():
    try:
        items = _get_frontend_group_labels()
    except Exception as err:
        logger.exception(log_event("aiida.frontend.groups.failed", error=str(err)))
        items = []
    return {"items": items}


@router.post("/frontend/profiles/switch")
async def frontend_switch_profile(payload: FrontendSwitchProfileRequest):
    profiles_display, _ = _get_sidebar_state()
    profile_names = {name for name, _display_name, _active in profiles_display}
    if payload.profile_name not in profile_names:
        raise HTTPException(status_code=404, detail="Profile not found")

    hub.switch_profile(payload.profile_name)
    profiles_display, _ = _get_sidebar_state()
    return {
        "current_profile": hub.current_profile,
        "profiles": _serialize_profiles(profiles_display),
    }


@router.post("/frontend/archives/upload")
async def frontend_upload_archive(file: UploadFile = File(...)):
    filename = file.filename or "archive.aiida"
    extension = Path(filename).suffix.lower()
    if extension not in ARCHIVE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported archive format")

    upload_root = Path(tempfile.gettempdir()) / "sabr-aiida-uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    target_name = f"{int(time.time() * 1000)}-{_sanitize_upload_name(filename)}"
    target_path = upload_root / target_name
    payload = await file.read()
    target_path.write_bytes(payload)
    await file.close()

    profile_name = hub.import_archive(target_path)
    profiles_display, _ = _get_sidebar_state()
    return {
        "status": "uploaded",
        "profile_name": profile_name,
        "stored_path": str(target_path),
        "profiles": _serialize_profiles(profiles_display),
    }


@router.get("/frontend/processes")
async def frontend_processes(
    limit: int = Query(default=15, ge=1, le=100),
    group_label: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
):
    try:
        processes = _get_frontend_nodes(limit=limit, group_label=group_label, node_type=node_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        logger.exception(log_event("aiida.frontend.processes.failed", error=str(err)))
        processes = []
    return {"items": _serialize_processes(processes)}


@router.get("/frontend/processes/stream")
async def frontend_processes_stream(
    request: Request,
    limit: int = Query(default=15, ge=1, le=100),
    group_label: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
):
    try:
        _get_frontend_nodes(limit=1, group_label=group_label, node_type=node_type)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    async def event_generator():
        stream_id = id(request)
        last_digest = ""
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.process_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.process_stream.disconnected", stream_id=stream_id))
                break

            try:
                processes = _serialize_processes(
                    _get_frontend_nodes(limit=limit, group_label=group_label, node_type=node_type)
                )
                digest = hashlib.sha1(json.dumps(processes, sort_keys=True).encode("utf-8")).hexdigest()
                now = time.monotonic()
                should_push = (digest != last_digest) or ((now - heartbeat_ts) >= 15)
                if should_push:
                    yield {"event": "processes", "data": json.dumps({"items": processes})}
                    last_digest = digest
                    heartbeat_ts = now
            except Exception as err:
                logger.exception(
                    log_event("aiida.frontend.process_stream.failed", stream_id=stream_id, error=str(err))
                )
                yield {"event": "processes", "data": json.dumps({"items": []})}

            await asyncio.sleep(1.5)

    return EventSourceResponse(event_generator())


@router.get("/frontend/logs")
async def frontend_logs(limit: int = Query(default=240, ge=20, le=1000)):
    version, lines = get_log_buffer_snapshot(limit=limit)
    return {"version": version, "lines": lines}


@router.get("/frontend/logs/stream")
async def frontend_logs_stream(request: Request, limit: int = Query(default=240, ge=20, le=1000)):
    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.log_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.log_stream.disconnected", stream_id=stream_id))
                break

            try:
                version, lines = get_log_buffer_snapshot(limit=limit)
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 8.0)
                if should_push:
                    yield {"event": "logs", "data": json.dumps({"version": version, "lines": lines})}
                    last_version = version
                    heartbeat_ts = now
            except Exception as err:
                logger.exception(
                    log_event("aiida.frontend.log_stream.failed", stream_id=stream_id, error=str(err))
                )
                yield {"event": "logs", "data": json.dumps({"version": -1, "lines": []})}

            await asyncio.sleep(0.75)

    return EventSourceResponse(event_generator())


@router.get("/frontend/chat/messages")
async def frontend_chat_messages(request: Request):
    state = request.app.state
    history = _serialize_chat_history(_get_chat_history(state))
    return {
        "version": int(getattr(state, "chat_version", 0)),
        "messages": history,
    }


@router.get("/frontend/chat/stream")
async def frontend_chat_stream(request: Request):
    state = request.app.state

    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(log_event("aiida.frontend.chat_stream.connected", stream_id=stream_id))
        while True:
            if await request.is_disconnected():
                logger.info(log_event("aiida.frontend.chat_stream.disconnected", stream_id=stream_id))
                break

            try:
                version = int(getattr(state, "chat_version", 0))
                history = _serialize_chat_history(_get_chat_history(state))
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 10)
                if should_push:
                    yield {
                        "event": "chat",
                        "data": json.dumps({"version": version, "messages": history}),
                    }
                    last_version = version
                    heartbeat_ts = now
            except Exception as err:
                logger.exception(
                    log_event("aiida.frontend.chat_stream.failed", stream_id=stream_id, error=str(err))
                )
                yield {"event": "chat", "data": json.dumps({"version": -1, "messages": []})}

            await asyncio.sleep(0.4)

    return EventSourceResponse(event_generator())


@router.post("/frontend/chat")
async def frontend_chat_submit(request: Request, payload: FrontendChatRequest):
    state = request.app.state
    user_intent = payload.intent.strip()
    if not user_intent:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    available_models = _get_available_models(state)
    selected_model = (
        payload.model_name
        if payload.model_name and payload.model_name in available_models
        else _get_selected_model(state, available_models)
    )
    state.selected_model = selected_model
    context_node_ids = _normalize_context_node_ids(payload.context_node_ids)

    turn_id = _start_chat_turn(
        state,
        user_intent=user_intent,
        selected_model=selected_model,
        context_archive=payload.context_archive,
        context_node_ids=context_node_ids,
        source="frontend",
    )
    return {
        "status": "queued",
        "turn_id": turn_id,
        "selected_model": selected_model,
        "version": int(getattr(state, "chat_version", 0)),
    }


@router.post("/frontend/chat/stop")
async def frontend_chat_stop(request: Request, payload: FrontendStopChatRequest):
    state = request.app.state
    cancelled_turn_id = _cancel_chat_turn(state, payload.turn_id)
    return {
        "status": "stopped" if cancelled_turn_id is not None else "idle",
        "turn_id": cancelled_turn_id,
        "version": int(getattr(state, "chat_version", 0)),
    }


# 1. Dashboard page (http://localhost:8000/ui/)
@router.get("/", response_model=FastUI, response_model_exclude_none=True)
async def aiida_ui_root(request: Request) -> FastUI:
    state = request.app.state
    # Treat engine root as "home": show clean welcome state.
    state.chat_history = []
    _touch_chat(state)
    logger.info(log_event("aiida.chat_history.reset_on_home"))
    return _render_chat_page(state)
 


@router.get("/archives/browse-local", response_model=FastUI)
async def trigger_native_browse():
    
    # 1. Open native file browser.
    # macOS requires NSWindow/Tk to run on the main thread.
    # Running this in a threadpool crashes with NSInternalInconsistencyException.
    selected_file = ask_for_folder_path()
    
    if selected_file:
        # Key path: register the archive dynamically.
        hub.import_archive(Path(selected_file))
        logger.info(log_event("aiida.archive.imported", path=selected_file))
    
    # 2. Force page refresh to reload the dashboard.
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/'))])

@router.get("/profiles/switch/{name}", response_model=FastUI)
async def handle_switch(name: str):
    # Switch profile in hub state.
    hub.switch_profile(name)
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/'))])

# 2. Chat input page (http://localhost:8000/aiida/chat)
# Triggered by "Start New Analysis" or direct navigation.
@router.get("/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_input_page(request: Request) -> FastUI:
    state = request.app.state
    return _render_chat_page(state)


@router.get("/chat/clear", response_model=FastUI)
async def clear_chat_history(request: Request):
    state = request.app.state
    state.chat_history = []
    _touch_chat(state)
    logger.info(log_event("aiida.chat_history.cleared"))
    return _render_chat_page(state)


@router.get("/chat/quick/{shortcut_id}", response_model=FastUI, response_model_exclude_none=True)
async def quick_chat_prompt(request: Request, shortcut_id: int) -> FastUI:
    state = request.app.state
    available_models = _get_available_models(state)
    selected_model = _get_selected_model(state, available_models)

    if shortcut_id < 0 or shortcut_id >= len(QUICK_PROMPTS):
        logger.warning(log_event("aiida.quick_chat.invalid_shortcut", shortcut_id=shortcut_id))
        return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])

    label, prompt = QUICK_PROMPTS[shortcut_id]
    logger.info(
        log_event(
            "aiida.quick_chat.selected",
            shortcut_id=shortcut_id,
            label=label,
            prompt=prompt,
            model=selected_model,
        )
    )
    if _debounce_request(state, key=f"quick:{shortcut_id}", window_seconds=5.0):
        logger.warning(log_event("aiida.quick_chat.debounced", shortcut_id=shortcut_id))
        return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])
    turn_id = _start_chat_turn(
        state,
        user_intent=prompt,
        selected_model=selected_model,
        context_archive=None,
        source=f"quick:{shortcut_id}",
    )
    logger.info(log_event("aiida.quick_chat.queued", shortcut_id=shortcut_id))
    logger.debug(log_event("aiida.quick_chat.turn_created", shortcut_id=shortcut_id, turn_id=turn_id))
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])

# 3. Agent execution endpoint and response rendering.
# FastUI automatically posts here on ModelForm submission.
@router.post("/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_handler(request: Request):
    """
    Core handler: run PydanticAI on form input and return rendered UI.
    """
    state = request.app.state
    user_intent, submitted_model, context_archive, context_node_ids = await _parse_chat_payload(request)

    available_models = _get_available_models(state)
    selected_model = submitted_model if submitted_model in available_models else _get_selected_model(state, available_models)
    state.selected_model = selected_model
    logger.info(
        log_event(
            "aiida.chat_handler.request",
            intent_len=len(user_intent),
            selected_model=selected_model,
            submitted_model=submitted_model,
            context=context_archive,
            context_node_ids=",".join(str(pk) for pk in context_node_ids) or None,
        )
    )

    if not user_intent:
        return _render_chat_page(state)

    context_ids_key = ",".join(str(pk) for pk in context_node_ids) or "-"
    dedupe_key = f"form:{selected_model}:{context_archive or '-'}:{context_ids_key}:{user_intent.strip().lower()}"
    if _debounce_request(state, key=dedupe_key, window_seconds=0.8):
        logger.warning(log_event("aiida.chat_handler.debounced", model=selected_model))
        return _render_chat_page(state)

    turn_id = _start_chat_turn(
        state,
        user_intent=user_intent,
        selected_model=selected_model,
        context_archive=context_archive,
        context_node_ids=context_node_ids,
        source="form",
    )
    logger.info(log_event("aiida.chat_handler.queued"))
    logger.debug(log_event("aiida.chat_handler.turn_created", turn_id=turn_id))
    return _render_chat_page(state)
