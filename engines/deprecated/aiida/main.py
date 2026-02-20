# engines/aiida/main.py
from nicegui import app, ui
from engines.aiida.web.web import create_layout
from src.sab_core.reporters.console import ConsoleReporter
from src.sab_core.memory.json_memory import JSONMemory
from src.sab_core.engine import SABEngine
from engines.aiida.perceptors.database import AIIDASchemaPerceptor
from engines.aiida.executors.executor import AiiDAExecutor
from engines.aiida.reporters.nicegui import NiceGUIReporter
from engines.aiida.controller import AiiDAController
from engines.aiida.brain_factory import create_aiida_brain
from src.sab_core.config import settings # Import your new config


def setup_engine(components, shared_memory):
    s_pcp = AIIDASchemaPerceptor()
    brain = create_aiida_brain(schema_info=s_pcp.perceive().raw)
    executor = AiiDAExecutor()
    reporters = [ConsoleReporter(), NiceGUIReporter(components)]
    
    # 2. Pass the shared_memory to the engine
    return SABEngine(
        perceptor=s_pcp, 
        brain=brain, 
        executor=executor, 
        reporters=reporters, 
        memory=shared_memory
    )

def main():
    # 1. 零件初始化
    components = create_layout(theme_name='oxford')
    shared_mem = JSONMemory(storage_dir=settings.MEMORY_DIR, namespace="global_config")
    engine = setup_engine(components, shared_memory=shared_mem)
    
    try:
        real_models = engine._brain.get_available_models()
        # 直接修改 NiceGUI 组件的 options 属性，界面会自动刷新
        components['model_select'].options = real_models
        # 如果你想默认选中第一个真实模型
        components['model_select'].value = real_models[0]
    except Exception as e:
        print(f"Failed to fetch models from brain: {e}")

    # 2. 逻辑控制器实例化
    ctrl = AiiDAController(engine, components, memory=shared_mem)
    
    # 3. 🚀 事件绑定 (一目了然)
    components['archive_select'].on_value_change(lambda e: ctrl.select_archive(e.value))
    components['upload_btn'].on('click', ctrl.pick_local_file)
    components['send_btn'].on('click', lambda: ctrl.handle_send())
    components['model_select'].on_value_change(ctrl.handle_model_change)
    components['controller'] = ctrl
    
    ui.on('node_clicked', ctrl.handle_node_inspection)
    
    # 绑定建议卡片
    for card, full_text in components['suggestion_cards']:
        card.on('click', lambda t=full_text: ctrl.handle_send(t))

    ui.run(port=8080, title="SABR-AiiDA", reload=True) # Windows 下建议 False

if __name__ in {"__main__", "__mp_main__"}:
    main()