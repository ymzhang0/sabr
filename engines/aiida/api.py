# engines/aiida/api.py
from fastapi import APIRouter, Request
from fastui import FastUI
from fastui import components as c
from fastui import events as e
from .ui.fastui import get_aiida_dashboard_layout, get_chat_interface
from src.sab_core.config import settings
from .ui import fastui as ui
from loguru import logger
from google import genai

import tkinter as tk
from tkinter import filedialog
from .hub import hub
from pathlib import Path
from .tools import get_recent_processes
from sse_starlette.sse import EventSourceResponse
import asyncio
import time
from contextlib import suppress
from typing import Any

def ask_for_folder_path():
    """
    Open a native file-selection dialog on the server host machine.
    """
    logger.info("🖥️ Opening native folder dialog on host OS...")
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
        logger.success(f"📂 User selected: {file_selected}")
        return file_selected
    else:
        logger.warning("🚫 User cancelled folder selection.")
        return None


router = APIRouter()
DEFAULT_MODELS = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
QUICK_PROMPTS: list[tuple[str, str]] = [
    ("Check Profile", "check the current profile"),
    ("List Groups", "list all groups in current profile"),
    ("DB Summary", "show database summary"),
]


def _get_sidebar_state() -> tuple[list, list]:
    """Load sidebar context for all dashboard-like pages."""
    if not hub.current_profile:
        hub.start()
    try:
        recent_procs = get_recent_processes(limit=5)
    except Exception as e:
        logger.error(f"Failed to fetch processes: {e}")
        recent_procs = []
    return hub.get_display_list(), recent_procs


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
        logger.warning(f"Failed to query GenAI models, using fallback list: {e}")
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
    return get_aiida_dashboard_layout(
        content=get_chat_interface(
            chat_history=_get_chat_history(state),
            model_name=selected_model,
            available_models=available_models,
            quick_shortcuts=_get_quick_shortcuts(),
        ),
        profiles_display=profiles_display,
        processes=recent_procs,
    )


def _ensure_chat_lock(state) -> asyncio.Lock:
    lock = getattr(state, "chat_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        state.chat_lock = lock
    return lock


def _update_assistant_message(state, turn_id: int, text: str, status: str = "thinking") -> None:
    chat_history = _get_chat_history(state)
    for msg in reversed(chat_history):
        if msg.get("role") == "assistant" and msg.get("turn_id") == turn_id:
            msg["text"] = text
            msg["status"] = status
            _touch_chat(state)
            logger.info(
                f"[ChatTurn {turn_id}] message_update | status={status} | chars={len(text)}"
            )
            return
    logger.warning(f"[ChatTurn {turn_id}] message_update missed | status={status}")


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
        f"[ChatTurn {turn_id}] message_append | status={status} | chars={len(text)}"
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


def _start_chat_turn(
    state,
    user_intent: str,
    selected_model: str,
    context_archive: str | None = None,
    source: str = "form",
) -> int:
    chat_history = _get_chat_history(state)
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
        f"[ChatTurn {turn_id}] queued | source={source} | model={selected_model} "
        f"| intent={user_intent[:120]!r} | context={context_archive!r}"
    )
    logger.info(f"[ChatTurn {turn_id}] queued_history | digest={_history_digest(chat_history)}")
    asyncio.create_task(
        _execute_chat_turn(
            state=state,
            turn_id=turn_id,
            user_intent=user_intent,
            selected_model=selected_model,
            context_archive=context_archive,
        )
    )
    return turn_id


async def _execute_chat_turn(
    state,
    turn_id: int,
    user_intent: str,
    selected_model: str,
    context_archive: str | None = None,
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
            f"[ChatTurn {turn_id}] start | model={selected_model} "
            f"| intent={user_intent[:120]!r} | context={context_archive!r}"
        )

        try:
            _update_assistant_message(
                state, turn_id, "Thinking: 正在初始化 AiiDA 依赖...", status="thinking"
            )
            current_deps = DepsClass(
                archive_path=context_archive,
                memory=state.memory
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
                f"[ChatTurn {turn_id}] done | run_id={getattr(result, 'run_id', None)} "
                f"| elapsed={elapsed:.2f}s | answer_chars={len(answer_text)} "
                f"| steps={len(getattr(current_deps, 'step_history', []) or [])}"
            )

            if hasattr(state, "memory") and state.memory:
                try:
                    state.memory.add_turn(
                        intent=user_intent,
                        response=answer_text,
                        metadata={"context_archive": context_archive},
                    )
                except Exception as mem_e:
                    logger.warning(f"Failed to persist chat turn: {mem_e}")

        except Exception as err:
            elapsed = time.perf_counter() - t0
            logger.exception(
                f"[ChatTurn {turn_id}] failed | elapsed={elapsed:.2f}s "
                f"| model={selected_model} | err={err}"
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


async def _parse_chat_payload(request: Request) -> tuple[str, str | None, str | None]:
    """
    Parse FastUI form payload safely to avoid 422 caused by strict model parsing.
    Returns (intent, model_name, context_archive).
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
        logger.warning(f"Failed to parse chat payload, fallback to empty body: {e}")

    intent = str(_first_value(raw.get("intent")) or "").strip()
    model_name = _first_value(raw.get("model_name"))
    context_archive = _first_value(raw.get("context_archive"))
    logger.info(
        f"[ChatPayload] keys={list(raw.keys())} | intent_len={len(intent)} "
        f"| model={model_name!r} | context={context_archive!r}"
    )
    return intent, (str(model_name) if model_name else None), (str(context_archive) if context_archive else None)

@router.get("/processes/stream")
async def stream_processes(request: Request):
    """
    SSE endpoint that pushes latest process status every 3 seconds.
    """
    async def event_generator():
        stream_id = id(request)
        logger.info(f"[ProcStream {stream_id}] connected")
        if not hub.current_profile:
            hub.start()
        while True:
            # Stop the stream when the client disconnects.
            if await request.is_disconnected():
                logger.info(f"[ProcStream {stream_id}] disconnected")
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
                logger.error(f"[ProcStream {stream_id}] error: {e}")
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


@router.get("/chat/messages/stream")
async def stream_chat_messages(request: Request):
    """
    SSE endpoint to live-update chat messages (including thinking states).
    """
    state = request.app.state

    async def event_generator():
        stream_id = id(request)
        last_version = -1
        heartbeat_ts = time.monotonic()
        logger.info(f"[ChatStream {stream_id}] connected")
        while True:
            if await request.is_disconnected():
                logger.info(f"[ChatStream {stream_id}] disconnected")
                break
            try:
                history = _get_chat_history(state)
                version = getattr(state, "chat_version", 0)
                now = time.monotonic()
                should_push = (version != last_version) or ((now - heartbeat_ts) >= 15)

                if should_push:
                    body = ui.get_chat_messages_panel(history)
                    yield {"data": FastUI(root=body).model_dump_json()}
                    logger.info(
                        f"[ChatStream {stream_id}] push | version={version} | messages={len(history)} "
                        f"| digest={_history_digest(history)} | {_history_layout_debug(history)} "
                        f"| {_history_ui_group_debug(history)}"
                    )
                    last_version = version
                    heartbeat_ts = now
            except Exception as err:
                logger.exception(f"[ChatStream {stream_id}] error: {err}")
                yield {
                    "data": FastUI(
                        root=[c.Div(class_name="text-muted small", components=[c.Text(text="Chat stream unavailable.")])]
                    ).model_dump_json()
                }
            await asyncio.sleep(0.25)

    return EventSourceResponse(event_generator())
      
# 1. Dashboard page (http://localhost:8000/ui/)
@router.get("/", response_model=FastUI, response_model_exclude_none=True)
async def aiida_ui_root(request: Request) -> FastUI:
    state = request.app.state
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
        logger.info(f"Dynamically expanded profiles with: {selected_file}")
    
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
    logger.info("[Chat] history cleared")
    return _render_chat_page(state)


@router.get("/chat/quick/{shortcut_id}", response_model=FastUI, response_model_exclude_none=True)
async def quick_chat_prompt(request: Request, shortcut_id: int) -> FastUI:
    state = request.app.state
    available_models = _get_available_models(state)
    selected_model = _get_selected_model(state, available_models)

    if shortcut_id < 0 or shortcut_id >= len(QUICK_PROMPTS):
        logger.warning(f"[QuickChat] invalid shortcut_id={shortcut_id}")
        return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])

    label, prompt = QUICK_PROMPTS[shortcut_id]
    logger.info(
        f"[QuickChat] id={shortcut_id} | label={label!r} | prompt={prompt!r} | model={selected_model}"
    )
    _start_chat_turn(
        state,
        user_intent=prompt,
        selected_model=selected_model,
        context_archive=None,
        source=f"quick:{shortcut_id}",
    )
    logger.info(f"[QuickChat] queued shortcut_id={shortcut_id}, redirecting to /aiida/chat")
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])

# 3. Agent execution endpoint and response rendering.
# FastUI automatically posts here on ModelForm submission.
@router.post("/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_handler(request: Request):
    """
    Core handler: run PydanticAI on form input and return rendered UI.
    """
    state = request.app.state
    user_intent, submitted_model, context_archive = await _parse_chat_payload(request)

    available_models = _get_available_models(state)
    selected_model = submitted_model if submitted_model in available_models else _get_selected_model(state, available_models)
    state.selected_model = selected_model
    logger.info(
        f"[ChatHandler] intent_len={len(user_intent)} | selected_model={selected_model} "
        f"| submitted_model={submitted_model!r}"
    )

    if not user_intent:
        return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])

    _start_chat_turn(
        state,
        user_intent=user_intent,
        selected_model=selected_model,
        context_archive=context_archive,
        source="form",
    )
    logger.info("[ChatHandler] turn queued, redirecting to /aiida/chat")
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/chat'))])
