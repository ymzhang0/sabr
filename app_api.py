# app_api.py
import os
import importlib
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 🚩 第一步：在所有逻辑开始前加载环境变量（用于代理和 API Key）
load_dotenv()

from src.sab_core.config import settings
from src.sab_core.factory import get_engine_instance
from src.sab_core.api.schemas import AgentRequest, AgentResponse

# 全局状态存储容器
state = {}

# ============================================================
# 🧬 生命周期管理 (Lifespan)
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    管理后端服务的启动和关闭。
    在这里完成 Engine 的组装、数据库连接和 AiiDA 环境检查。
    """
    print(f"🚀 [Backend] Starting SABR-API (2026 Edition)")
    print(f"🌐 [Proxy] Current HTTP_PROXY: {os.getenv('HTTP_PROXY')}")
    
    try:
        # 1. 动态获取引擎实例 (根据 settings.ENGINE_TYPE)
        print(f"🧬 [Engine] Initializing '{settings.ENGINE_TYPE}' engine...")
        state["engine"] = get_engine_instance()
        
        # 2. 验证引擎是否就绪
        if state["engine"]:
            print(f"✅ [Engine] {settings.ENGINE_TYPE.upper()} is ready.")
        
    except Exception as e:
        print(f"❌ [Backend] Startup failed: {e}")
        # 这里不 raise，让服务带病运行以便通过 API 报错，而不是直接崩溃
    
    yield
    # 3. 清理工作
    state.clear()
    print("🛑 [Backend] SABR-API shut down.")

# ============================================================
# 🛠️ FastAPI 实例初始化
# ============================================================
app = FastAPI(
    title="SABR Research API",
    description="Decoupled Agentic Backend for AiiDA & Science Agents",
    version="1.0.0",
    lifespan=lifespan
)

# 允许跨域（如果前端 app_web.py 在不同机器或端口上运行）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 🚩 动态挂载引擎特有路由 (Router Mounting)
# ============================================================
def mount_engine_api():
    """
    自动发现并挂载 engines/{engine_name}/api.py 中的路由。
    例如：/v1/aiida/processes, /v1/aiida/nodes/{pk}
    """
    engine_name = settings.ENGINE_TYPE
    try:
        api_module = importlib.import_module(f"engines.{engine_name}.api")
        if hasattr(api_module, "router"):
            app.include_router(api_module.router, prefix="/v1")
            print(f"🔗 [Router] Mounted specific API for '{engine_name}'")
    except ImportError:
        print(f"ℹ️ [Router] No extra API routes found for '{engine_name}'.")
    except Exception as e:
        print(f"⚠️ [Router] Failed to mount engine routes: {e}")

mount_engine_api()

# ============================================================
# 🛣️ 通用公共端点 (Public Endpoints)
# ============================================================

@app.post("/v1/chat", response_model=AgentResponse)
async def chat_endpoint(req: AgentRequest):
    """
    通用聊天接口。接收用户意图，返回 AI 回复和执行结果。
    """
    engine = state.get("engine")
    if not engine:
        raise HTTPException(status_code=503, detail="SABR Engine is not initialized.")
    
    # 构造带上下文的意图
    intent = req.intent
    if req.context_archive and req.context_archive != "(None)":
        # 如果是 AiiDA 引擎，自动注入档案背景
        intent = f"Context: Inspect archive '{req.context_archive}'. Task: {intent}"

    try:
        # 执行 Agent 决策循环 (Run-Once 模式)
        response_data = await engine.run_once(intent=intent)
        
        # 将 EngineResponse 映射为符合 API Schema 的字典
        return AgentResponse(
            content=response_data.get("content", ""),
            action_name=response_data.get("action_name", "unknown"),
            result=response_data.get("result"),
            suggestions=response_data.get("suggestions", [])
        )
    except Exception as e:
        print(f"🔥 [Chat Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/models")
async def list_models():
    """获取当前 Brain 支持的所有可用模型名称列表"""
    engine = state.get("engine")
    if engine and hasattr(engine._brain, 'get_available_models'):
        return {"models": engine._brain.get_available_models()}
    return {"models": ["gemini-2.0-flash", "gemini-1.5-pro"]}

@app.get("/health")
async def health_check():
    """服务健康状况检查"""
    return {
        "status": "healthy", 
        "engine": settings.ENGINE_TYPE,
        "initialized": "engine" in state
    }

# ============================================================
# 🏁 启动服务
# ============================================================
if __name__ == "__main__":
    import uvicorn
    # 使用 8000 端口，生产环境建议 host 设为 0.0.0.0
    uvicorn.run(app, host="127.0.0.1", port=8000)