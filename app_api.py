import logging
from loguru import logger

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # 尝试获取对应的 Loguru 级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 找到调用者的位置
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# 1. 先清除所有现有的 handler
logging.getLogger().handlers = [InterceptHandler()]

# 2. 🚩 重点：显式地针对 uvicorn 的三个关键 logger 进行重定向
for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    mod_logger = logging.getLogger(logger_name)
    mod_logger.handlers = [InterceptHandler()]
    mod_logger.propagate = False  # 禁止向上传递，防止重复打印

# 3. 设置根日志级别
logging.getLogger().setLevel(logging.INFO)

import importlib
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 1. Load environment variables at the very beginning (Proxy, API Keys)
load_dotenv()

from src.sab_core.config import settings
from src.sab_core.memory.json_memory import JSONMemory
from src.sab_core.schema import AgentRequest, SABRResponse
from src.sab_core.schema.response import SABRResponse

from fastui import prebuilt_html
from fastapi.responses import HTMLResponse

from engines.aiida.hub import hub as aiida_hub

# Global state container for long-lived objects
state = {}
# 🚩 动态 Hub 注册表
ACTIVE_HUBS = []
# ============================================================
# 🧬 Lifespan Management
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown logic for the SABR Hub.
    """
    logger.info(f"🚀 [SABR v2] Initializing Backend Hub...")
    
    # Initialize Global Memory
    state["memory"] = JSONMemory(
        namespace="sabr_v2_global",
        storage_path=settings.SABR_MEMORY_DIR  # Now it's dynamic!
        )
    
    # Dynamically load the engine-specific agent and deps
    engine_name = settings.ENGINE_TYPE  # e.g., 'aiida'
    try:
        # Load the Researcher Agent from the engine folder
        # e.g., from engines.aiida.agents.researcher import aiida_researcher
        agent_module = importlib.import_module(f"engines.{engine_name}.agents.researcher")
        state["agent"] = getattr(agent_module, f"{engine_name}_researcher")
        
        # Load the specific Deps class
        # e.g., from engines.aiida.deps import AiiDADeps
        deps_module = importlib.import_module(f"engines.{engine_name}.deps")
        state["deps_class"] = getattr(deps_module, settings.DEPS_CLASS)
        
        logger.info(f"✅ [Agent] '{engine_name}' expert agent is online.")

        # 4. 🚩 动态挂载专属前端入口: http://localhost:8000/aiida/
        @app.get(f"/{engine_name}/{{path:path}}", response_class=HTMLResponse)
        async def engine_frontend(path: str):
            return prebuilt_html(
                api_root_url='/api',  # 保持 /api 根路径
                title=f"SABR | {engine_name.upper()}"
            )
            
        logger.info(f"✅ Engine '{engine_name}' mounted at /{engine_name}")

        for hub in ACTIVE_HUBS:
            if hasattr(hub, 'start'):
                hub.start()
                
    except Exception as e:
        logger.info(f"❌ [Critical] Failed to load agent/deps for {engine_name}: {e}")
  
    yield
    logger.info("🛑 [Framework] Shutting down active engines...")
    
    yield
    # Cleanup logic
    state.clear()
    logger.info("🛑 [SABR v2] Hub shut down.")

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
    按需挂载引擎：
    1. 挂载路由
    2. 注册该引擎的 Hub 到启动列表
    """
    try:
        # 动态导入路由和 Hub
        api_module = importlib.import_module(f"engines.{engine_name}.api")
        hub_module = importlib.import_module(f"engines.{engine_name}.hub")
        
        # 1. 挂载路由
        app.include_router(api_module.router, prefix=f"/api/{engine_name}")
        
        # 2. 注册 Hub
        if hasattr(hub_module, 'hub'):
            ACTIVE_HUBS.append(hub_module.hub)
            logger.info(f"🔗 [Registry] Engine '{engine_name}' registered for startup.")
            
    except Exception as e:
        logger.error(f"❌ [Registry] Failed to mount engine '{engine_name}': {e}")

mount_engine(app, "aiida")

# ============================================================
# 🛣️ Core Agent Endpoint (The Cyclic Hub)
# ============================================================

# 外部仅放承载 FastUI 的路由
@app.get('/ui/{path:path}')
async def fastui_frontend(path: str) -> HTMLResponse:
    return HTMLResponse(prebuilt_html(
        api_root_url='/api',  #
        title='SABR v2'
    ))
# ============================================================
# 🏁 Execution Entry
# ============================================================
if __name__ == "__main__":
    import uvicorn
    # Listening on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)