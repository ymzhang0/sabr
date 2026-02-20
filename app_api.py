import os
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

# Global state container for long-lived objects
state = {}

# ============================================================
# 🧬 Lifespan Management
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown logic for the SABR Hub.
    """
    print(f"🚀 [SABR v2] Initializing Backend Hub...")
    
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
        state["deps_class"] = getattr(deps_module, f"{engine_name.capitalize()}Deps")
        
        print(f"✅ [Agent] '{engine_name}' expert agent is online.")
    except Exception as e:
        print(f"❌ [Critical] Failed to load agent/deps for {engine_name}: {e}")
    
    yield
    # Cleanup logic
    state.clear()
    print("🛑 [SABR v2] Hub shut down.")

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
def mount_specific_routes():
    """
    Mounts additional API endpoints defined inside engine folders.
    Example: engines/aiida/api.py -> /v1/aiida/...
    """
    engine_name = settings.ENGINE_TYPE
    try:
        api_mod = importlib.import_module(f"engines.{engine_name}.api")
        if hasattr(api_mod, "router"):
            app.include_router(api_mod.router, prefix="/v1")
            print(f"🔗 [Router] Mounted specific routes for {engine_name}")
    except ImportError:
        pass

mount_specific_routes()

# ============================================================
# 🛣️ Core Agent Endpoint (The Cyclic Hub)
# ============================================================

@app.post("/v1/chat", response_model=SABRResponse)
async def chat_endpoint(req: AgentRequest):
    """
    Main entry point for user interaction. 
    Triggers the PydanticAI cyclic reasoning loop.
    """
    agent = state.get("agent")
    DepsClass = state.get("deps_class")
    
    if not agent or not DepsClass:
        raise HTTPException(status_code=503, detail="Agent system not fully initialized.")

    # 1. Instantiate the 'Blood' (Deps) for this specific request cycle
    # This carries the archive path and shared state into the loop.
    current_deps = DepsClass(
        archive_path=req.context_archive,
        memory=state["memory"]
    )

    try:
        # 2. Execute the Cyclic Graph: Think -> Tool -> Observe -> Repeat
        # PydanticAI handles the internal iteration until SABRResponse is satisfied.
        result = await agent.run(req.intent, deps=current_deps)
        
        # 3. Extract the validated Pydantic model
        # The 'result.data' is guaranteed to follow the SABRResponse schema.
        response_data = result.data
        
        # Enrich the response with the step history captured in Deps
        if hasattr(current_deps, "step_history"):
            response_data.thought_process = current_deps.step_history
            
        return response_data

    except Exception as e:
        print(f"🔥 [Agent Loop Error] {str(e)}")
        # In case of cyclic failure, we return a structured error response
        return SABRResponse(
            answer=f"I encountered a technical issue during analysis: {str(e)}",
            thought_process=["Error occurred during reasoning cycle."],
            is_successful=False,
            suggestions=["Retry query", "Check AiiDA status"]
        )

# ============================================================
# 🏁 Execution Entry
# ============================================================
if __name__ == "__main__":
    import uvicorn
    # Listening on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)