from __future__ import annotations

import importlib
import os
from contextlib import asynccontextmanager

from loguru import logger
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.sab_core.logging_utils import get_log_buffer_snapshot, log_event, setup_logging

# 1. Load environment variables at the very beginning (Proxy, API Keys)
load_dotenv()
setup_logging(default_level="INFO")
logger.info(log_event("logging.ready"))

from src.sab_core.config import settings
from src.sab_core.memory.json_memory import JSONMemory

from fastui import prebuilt_html
from html import escape

FASTUI_INLINE_CSS = """
<style>
.sabr-log-terminal {
    height: 220px;
    overflow-y: auto;
    overflow-x: auto;
    scrollbar-width: thin;
}
.sabr-log-line {
    font-size: 10px;
    line-height: 1.2;
    white-space: pre;
}
</style>
"""


def _prebuilt_html_with_styles(api_root_url: str, title: str) -> str:
    html = prebuilt_html(api_root_url=api_root_url, title=title)
    if "</head>" in html:
        return html.replace("</head>", FASTUI_INLINE_CSS + "</head>")
    return html + FASTUI_INLINE_CSS

# Global state container for long-lived objects
state = {}
# Dynamic hub registry.
ACTIVE_HUBS = []
# ============================================================
# 🧬 Lifespan Management
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown logic for the SABR Hub.
    """
    logger.info(log_event("hub.startup.begin"))
    
    # Initialize Global Memory
    memory = JSONMemory(
        namespace="sabr_v2_global",
        storage_path=settings.SABR_MEMORY_DIR  # Now it's dynamic!
        )
    state["memory"] = memory
    app.state.memory = memory
    
    # Dynamically load the engine-specific agent and deps
    engine_name = settings.ENGINE_TYPE  # e.g., 'aiida'
    try:
        # Load the Researcher Agent from the engine folder
        # e.g., from engines.aiida.agents.researcher import aiida_researcher
        agent_module = importlib.import_module(f"engines.{engine_name}.agents.researcher")
        agent = getattr(agent_module, f"{engine_name}_researcher")
        state["agent"] = agent
        app.state.agent = agent
        
        # Load the specific Deps class
        # e.g., from engines.aiida.deps import AiiDADeps
        deps_module = importlib.import_module(f"engines.{engine_name}.deps")
        deps_class = getattr(deps_module, settings.DEPS_CLASS)
        state["deps_class"] = deps_class
        app.state.deps_class = deps_class
        
        logger.info(log_event("engine.agent.online"))

        for hub in ACTIVE_HUBS:
            if hasattr(hub, 'start'):
                hub.start()
                
    except Exception as e:
        logger.exception(log_event("engine.bootstrap.failed", engine=engine_name, error=str(e)))
  
    yield
    logger.info(log_event("hub.shutdown.begin"))
    # Cleanup logic
    state.clear()
    logger.info(log_event("hub.shutdown.done"))

# ============================================================
# 🛠️ FastAPI Application Setup
# ============================================================
app = FastAPI(
    title="SABR v2 Central Hub",
    description="Multi-Agent Scientific Research Bus powered by PydanticAI",
    lifespan=lifespan
)

LEGACY_STATIC_DIR = os.path.join(os.getcwd(), "engines", "aiida", "static")
FRONTEND_DIST_DIR = settings.FRONTEND_DIST_DIR
FRONTEND_ASSETS_DIR = settings.FRONTEND_ASSETS_DIR
FRONTEND_INDEX_FILE = settings.FRONTEND_INDEX_FILE

if os.path.isdir(LEGACY_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=LEGACY_STATIC_DIR), name="static")

if os.path.isdir(FRONTEND_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")
else:
    logger.warning(log_event("frontend.assets.missing", path=FRONTEND_ASSETS_DIR))


def _get_cors_origins() -> list[str]:
    required = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://sabr.yiming-zhang.com",
    }
    raw = settings.SABR_FRONTEND_ORIGINS or ""
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return sorted(values | required)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 🚩 Engine-Specific Route Mounting
# ============================================================
def mount_engine(app: FastAPI, engine_name: str):
    """
    Mount an engine on demand:
    1. Register routes.
    2. Register the engine hub for startup.
    """
    try:
        # Dynamically import router and hub modules.
        api_module = importlib.import_module(f"engines.{engine_name}.api")
        hub_module = importlib.import_module(f"engines.{engine_name}.hub")
        
        # 1. Mount routes.
        app.include_router(api_module.router, prefix=f"/api/{engine_name}")
        
        # 2. Register hub.
        if hasattr(hub_module, 'hub'):
            ACTIVE_HUBS.append(hub_module.hub)
            logger.info(log_event("engine.registry.registered", engine=engine_name))
            
    except Exception as e:
        logger.exception(log_event("engine.registry.failed", engine=engine_name, error=str(e)))

mount_engine(app, "aiida")


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/api/aiida/logs/copy", response_class=HTMLResponse)
async def aiida_logs_copy_page():
    """Open a tiny helper page and copy latest runtime logs to clipboard."""
    _, lines = get_log_buffer_snapshot(limit=240)
    payload = "\n".join(lines[-120:]) if lines else "No logs yet."
    safe_payload = escape(payload)
    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Copy Logs</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }}
    textarea {{ width: 100%; height: 280px; }}
    .muted {{ color: #666; font-size: 13px; }}
  </style>
</head>
<body>
  <p class="muted">Copying runtime logs… If browser blocks clipboard, use the textarea below.</p>
  <textarea id="logs">{safe_payload}</textarea>
  <script>
    const text = document.getElementById('logs').value;
    const done = () => {{ document.querySelector('.muted').textContent = 'Logs copied to clipboard.'; }};
    const fail = () => {{ document.querySelector('.muted').textContent = 'Clipboard blocked. Press Cmd/Ctrl+C to copy.'; }};
    (async () => {{
      try {{
        await navigator.clipboard.writeText(text);
        done();
      }} catch (e) {{
        fail();
      }}
      const ta = document.getElementById('logs');
      ta.focus();
      ta.select();
    }})();
  </script>
</body>
</html>
"""
    return HTMLResponse(html)


# ============================================================
# 🛣️ Core Agent Endpoint (The Cyclic Hub)
# ============================================================

# External-only route for hosting the FastUI shell.
@app.get('/ui/{_path:path}')
async def fastui_frontend(_path: str = "") -> HTMLResponse:
    return HTMLResponse(_prebuilt_html_with_styles(
        api_root_url='/api',
        title='SABR v2'
    ))


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catch_all(full_path: str = ""):
    if full_path.startswith("api") or full_path.startswith("assets") or full_path.startswith("static"):
        return HTMLResponse("Not Found", status_code=404)

    if not os.path.isfile(FRONTEND_INDEX_FILE):
        logger.warning(
            log_event(
                "frontend.index.missing",
                path=FRONTEND_INDEX_FILE,
                dist=FRONTEND_DIST_DIR,
            )
        )
        return HTMLResponse("Frontend build not found.", status_code=404)

    return FileResponse(FRONTEND_INDEX_FILE)
# ============================================================
# 🏁 Execution Entry
# ============================================================
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Run SABR API server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument(
        "--log-level",
        default=os.getenv("SABR_LOG_LEVEL", "INFO"),
        choices=["TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"],
    )
    args = parser.parse_args()

    os.environ["SABR_LOG_LEVEL"] = str(args.log_level).upper()
    setup_logging(default_level=str(args.log_level).upper())
    logger.info(
        log_event(
            "server.run",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=str(args.log_level).upper(),
        )
    )
    reload_excludes: list[str] = []
    if args.reload:
        memory_dir = str(settings.SABR_MEMORY_DIR or "").strip()
        if memory_dir:
            cleaned = memory_dir.rstrip("/").rstrip("\\")
            reload_excludes.extend([cleaned, f"{cleaned}/*"])
        # Common local memory folders used in this repo.
        reload_excludes.extend([
            "engines/aiida/data/memories",
            "engines/aiida/data/memories/*",
            "default",
            "default/*",
        ])
    uvicorn.run(
        "app_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_excludes=reload_excludes or None,
        log_config=None,
    )
