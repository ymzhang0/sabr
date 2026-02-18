# engines/aiida/main.py
from nicegui import ui
from engines.aiida.web.web import create_layout
from src.sab_core.reporters.console import ConsoleReporter
from src.sab_core.memory.json_memory import JSONMemory
from src.sab_core.engine import SABEngine
from engines.aiida.perceptors.database import AIIDASchemaPerceptor
from engines.aiida.executors.executor import AiiDAExecutor
from engines.aiida.reporters.nicegui import NiceGUIReporter
from engines.aiida.controller import AiiDAController
from engines.aiida.brain_factory import create_aiida_brain

def setup_engine(components):
    """专门负责初始化后端引擎零件"""
    s_pcp = AIIDASchemaPerceptor()
    brain = create_aiida_brain(schema_info=s_pcp.perceive().raw)
    executor = AiiDAExecutor()
    reporters = [ConsoleReporter(), NiceGUIReporter(components)]
    memory=JSONMemory(storage_dir="engines/aiida/data/memories", namespace="global_config"),
    return SABEngine(perceptor=s_pcp, brain=brain, executor=executor, reporters=reporters, memory=memory)
def main():
    # 1. 零件初始化
    components = create_layout()
    engine = setup_engine(components) # 提取出的引擎初始化逻辑
    
    # 2. 逻辑控制器实例化
    ctrl = AiiDAController(engine, components)
    
    # 3. 🚀 事件绑定 (一目了然)
    components['archive_select'].on_value_change(lambda e: ctrl.select_archive(e.value))
    components['upload_btn'].on('click', ctrl.pick_local_file)
    components['send_btn'].on('click', lambda: ctrl.handle_send())
    ui.on('node_clicked', ctrl.handle_node_inspection)
    
    # 绑定建议卡片
    for card, full_text in components['suggestion_cards']:
        card.on('click', lambda t=full_text: ctrl.handle_send(t))

    ui.run(port=8080, title="SABR-AiiDA", reload=False) # Windows 下建议 False

if __name__ in {"__main__", "__mp_main__"}:
    main()