from __future__ import annotations

import importlib
from contextlib import asynccontextmanager

from loguru import logger
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.sab_core.logging_utils import log_event, setup_logging

# 1. Load environment variables at the very beginning (Proxy, API Keys)
load_dotenv()
setup_logging(default_level="INFO")
logger.info(log_event("logging.ready"))

from src.sab_core.config import settings
from src.sab_core.memory.json_memory import JSONMemory

from fastui import prebuilt_html
from fastapi.responses import HTMLResponse

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

        # 4. Dynamically mount the engine-specific frontend entry point.
        @app.get(f"/{engine_name}/{{_path:path}}", response_class=HTMLResponse)
        async def engine_frontend(_path: str = ""):
            return _prebuilt_html_with_styles(
                api_root_url='/api',  # Keep the shared /api root path.
                title=f"SABR | {engine_name.upper()}"
            )
            
        logger.info(log_event("engine.frontend.mounted", path=f"/{engine_name}"))

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
# ============================================================
# 🏁 Execution Entry
# ============================================================
if __name__ == "__main__":
    import argparse
    import os
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
    uvicorn.run(
        "app_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,
    )
