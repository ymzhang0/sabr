# engines/aiida/api.py
from fastapi import APIRouter, Request
from fastui import FastUI
from fastui import components as c
from fastui import events as e
from .ui.fastui import get_aiida_dashboard_layout, get_chat_interface, render_sabr_response
from sab_core.schema.request import AgentRequest
from .ui import fastui as ui
from loguru import logger

from fastapi.concurrency import run_in_threadpool
import tkinter as tk
from tkinter import filedialog
from .hub import hub
from pathlib import Path
from .tools import get_recent_processes
from sse_starlette.sse import EventSourceResponse
import asyncio

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

@router.get("/processes/stream")
async def stream_processes(request: Request):
    """
    SSE endpoint that pushes latest process status every 3 seconds.
    """
    async def event_generator():
        while True:
            # Stop the stream when the client disconnects.
            if await request.is_disconnected():
                break

            # 1. Fetch latest process data.
            try:
                # Ensure this query path stays fast enough for polling.
                processes = get_recent_processes()
                
                # 2. Build and push only the process panel components.
                body = ui.get_process_panel(processes)
                
                # 3. Wrap payload in FastUI JSON.
                yield {
                    "data": FastUI(root=[body]).model_dump_json()
                }
            except Exception as e:
                logger.error(f"Streaming error: {e}")

            # 4. Throttle update frequency.
            await asyncio.sleep(3)

    return EventSourceResponse(event_generator())
      
# 1. Dashboard page (http://localhost:8000/ui/)
@router.get("/", response_model=FastUI, response_model_exclude_none=True)
async def aiida_ui_root() -> FastUI:

    hub.start()
    # 2. Fetch recent tasks via the tool layer.
    try:
        # Database query logic is encapsulated inside tools.
        recent_procs = get_recent_processes(limit=5)
    except Exception as e:
        logger.error(f"Failed to fetch processes: {e}")
        recent_procs = []

    # 3. Build the default main-content view.
    chat_content = ui.get_chat_interface()

    # 4. Render full dashboard layout.
    return ui.get_aiida_dashboard_layout(
        content=chat_content,
        profiles_display=hub.get_display_list(),
        processes=recent_procs  # Inject process data.
    )
 


@router.get("/archives/browse-local", response_model=FastUI)
async def trigger_native_browse():
    
    # 1. Open native file browser.
    selected_file = await run_in_threadpool(ask_for_folder_path)
    
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
@router.get("/aiida/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_input_page() -> FastUI:
    # Return the ModelForm defined in fastui.py.
    return get_aiida_dashboard_layout(get_chat_interface())

# 3. Agent execution endpoint and response rendering.
# FastUI automatically posts here on ModelForm submission.
@router.post("/aiida/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_handler(request: Request, form: AgentRequest):
    """
    Core handler: run PydanticAI on form input and return rendered UI.
    """
    state = request.app.state
    agent = getattr(state, "agent", None)
    DepsClass = getattr(state, "deps_class", None)
    
    # Extract user intent from form.
    user_intent = form.intent 
    context_archive = form.context_archive

    try:
        # Initialize dependencies and run the agent.
        current_deps = DepsClass(
            archive_path=context_archive,
            memory=state.memory
        )
        
        # Run PydanticAI cycle.
        result = await agent.run(user_intent, deps=current_deps)
        
        # Attach reasoning trace when available.
        if hasattr(current_deps, "step_history"):
            result.data.thought_process = current_deps.step_history
            
        # Return the pre-rendered result layout.
        return get_aiida_dashboard_layout(render_sabr_response(result.data))

    except Exception as e:
        return get_aiida_dashboard_layout([
            c.Heading(text="Analysis Error", level=2),
            c.Markdown(text=f"Something went wrong: `{str(e)}`"),
            c.Button(text="Back to Chat", on_click=c.GoToEvent(url='/aiida/chat'))
        ])
