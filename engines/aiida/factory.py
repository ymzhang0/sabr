# engines/aiida/factory.py
from engines.aiida.perceptors.database import AIIDASchemaPerceptor
from engines.aiida.executors.executor import AiiDAExecutor
from engines.aiida.brain_factory import create_aiida_brain
from sab_core.engine import SABEngine
from sab_core.memory.json_memory import JSONMemory
from sab_core.config import settings

def create_engine():
    """这是 AiiDA 引擎的专用工厂函数"""
    s_pcp = AIIDASchemaPerceptor()
    brain = create_aiida_brain(schema_info=s_pcp.perceive().raw)
    executor = AiiDAExecutor()
    memory = JSONMemory(storage_dir=settings.MEMORY_DIR, namespace="aiida_remote")
    
    return SABEngine(
        perceptor=s_pcp,
        brain=brain,
        executor=executor,
        memory=memory
    )