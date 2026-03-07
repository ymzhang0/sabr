from __future__ import annotations

import importlib
import os
from contextlib import asynccontextmanager

from loguru import logger
from dotenv import load_dotenv
from fastapi import FastAPI, Query
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

from html import escape

# Global state container for long-lived objects
state = {}
# Dynamic hub registry.
ACTIVE_HUBS = []
DEFAULT_ENGINE = "aiida"


def _configure_proxy_environment() -> None:
    """Normalize proxy environment variables from SABR settings."""
    use_proxy = bool(settings.SABR_USE_OUTBOUND_PROXY)
    http_proxy = str(settings.HTTP_PROXY or "").strip() if use_proxy else ""
    https_proxy = str(settings.HTTPS_PROXY or "").strip() if use_proxy else ""

    # Clear or set environment variables
    for env_key in ("HTTP_PROXY", "http_proxy"):
        if http_proxy:
            os.environ[env_key] = http_proxy
        else:
            os.environ.pop(env_key, None)

    for env_key in ("HTTPS_PROXY", "https_proxy"):
        if https_proxy:
            os.environ[env_key] = https_proxy
        else:
            os.environ.pop(env_key, None)

    # Ensure localhost traffic is never proxied
    no_proxy_raw = str(os.getenv("NO_PROXY") or os.getenv("no_proxy") or "").strip()
    no_proxy_items = {item.strip() for item in no_proxy_raw.split(",") if item.strip()}
    no_proxy_items.update({"127.0.0.1", "localhost", "::1"})
    no_proxy_value = ",".join(sorted(no_proxy_items))
    os.environ["NO_PROXY"] = no_proxy_value
    os.environ["no_proxy"] = no_proxy_value

    logger.info(
        log_event(
            "network.proxy.configured",
            use_proxy=use_proxy,
            http_proxy=bool(http_proxy),
            https_proxy=bool(https_proxy),
            no_proxy=no_proxy_value,
        )
    )


_configure_proxy_environment()
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
    engine_name = (settings.ENGINE_TYPE or "").strip() or DEFAULT_ENGINE
    try:
        # Load the Researcher Agent from the engine folder
        # e.g., from src.sab_engines.aiida.agent.researcher import aiida_researcher
        agent_module = importlib.import_module(f"src.sab_engines.{engine_name}.agent.researcher")
        agent = getattr(agent_module, f"{engine_name}_researcher")
        state["agent"] = agent
        app.state.agent = agent
        
        # Load the specific Deps class
        # e.g., from src.sab_engines.aiida.deps import AiiDADeps
        deps_module = importlib.import_module(f"src.sab_engines.{engine_name}.deps")
        configured_deps_class = (settings.DEPS_CLASS or "").strip()
        if configured_deps_class and hasattr(deps_module, configured_deps_class):
            deps_class_name = configured_deps_class
        else:
            deps_class_name = getattr(deps_module, "DEFAULT_DEPS_CLASS", "AiiDADeps")
        deps_class = getattr(deps_module, deps_class_name)
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

LEGACY_STATIC_DIR = os.path.join(os.getcwd(), "src", "sab_engines", "aiida", "static")
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
        # Dynamically import unified engine router and hub modules.
        router_module = importlib.import_module(f"src.sab_engines.{engine_name}.router")
        hub_module = importlib.import_module(f"src.sab_engines.{engine_name}.hub")
        
        # 1. Mount routes.
        app.include_router(router_module.router, prefix=f"/api/{engine_name}")
        
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


@app.get("/api/specializations/active")
async def specializations_active(
    context_node_ids: list[int] | None = Query(default=None),
    project_tags: list[str] | None = Query(default=None),
    resource_plugins: list[str] | None = Query(default=None),
    selected_environment: str | None = Query(default=None),
    auto_switch: bool = Query(default=True),
):
    from src.sab_engines.aiida.specializations import build_active_specializations_payload

    return await build_active_specializations_payload(
        context_node_ids=context_node_ids,
        project_tags=project_tags,
        resource_plugins=resource_plugins,
        selected_environment=selected_environment,
        auto_switch=auto_switch,
    )


@app.get("/api/aiida/logs/copy", response_class=HTMLResponse)
async def aiida_logs_copy_page():
    """Open a tiny helper page and copy latest runtime logs to clipboard."""
    _, lines = get_log_buffer_snapshot(limit=240)
    payload = "\n".join(lines[-120:]) if lines else "No logs yet."
    safe_payload = escape(payload)
    
    template_path = os.path.join(os.getcwd(), "src", "sab_engines", "aiida", "static", "logs_template.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
            html = template.replace("{{safe_payload}}", safe_payload)
            return HTMLResponse(html)
    except Exception as error:
        logger.error(log_event("aiida.logs.template.missing", path=template_path, error=str(error)))
        return HTMLResponse(f"<html><body><pre>{safe_payload}</pre></body></html>")


# ============================================================
# 🛣️ Core Agent Endpoint (The Cyclic Hub)
# ============================================================

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
            "src/sab_engines/aiida/data/memories",
            "src/sab_engines/aiida/data/memories/*",
            # Script archive files are generated during chat turns; exclude to prevent
            # dev hot-reload from killing active SSE/stream responses.
            "src/sab_engines/aiida/data/scripts",
            "src/sab_engines/aiida/data/scripts/*",
            "default",
            "default/*",
        ])
    uvicorn.run(
        "src.app_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_excludes=reload_excludes or None,
        log_config=None,
    )
