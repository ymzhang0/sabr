from nicegui import ui
from sab_core.engine import SABEngine
from sab_core.reporters.console import ConsoleReporter
from engines.aiida.perceptors.database import AIIDASchemaPerceptor
from engines.aiida.perceptors.human import HumanPerceptor
from engines.aiida.brain_factory import create_aiida_brain
from engines.aiida.web.web import create_layout
from engines.aiida.reporters.nicegui import NiceGUIReporter
from engines.aiida.executor import AiiDAExecutor 

def main():
    # --- 初始化 UI ---
    components = create_layout()
    
    # --- 初始化零件 ---
    h_pcp = HumanPerceptor()
    s_pcp = AIIDASchemaPerceptor()
    
    # 获取初始上下文
    initial_schema = s_pcp.perceive().raw
    brain = create_aiida_brain(schema_info=initial_schema)
    
    # --- 组装 Reporters (注意这里用了 BaseReporter 血统) ---
    console_rep = ConsoleReporter()
    web_rep = NiceGUIReporter(components)
    
    # --- 初始化执行器 ---
    executor = AiiDAExecutor()

    # --- 初始化 Engine ---
    engine = SABEngine(
        perceptor=s_pcp, # 这里暂时由 SchemaPerceptor 主导，Human 作为辅助
        brain=brain,
        executor=executor, # 这里以后接你的 AiiDA 执行器
        reporters=[console_rep, web_rep]
    )

    # --- 绑定发送逻辑 ---
    async def handle_send():
        text = components['input'].value
        selected_arch = components['archive_select'].value
        if not text: return
        
        # 1. 立即清空输入，防止卡顿
        components['input'].value = ""
        
        # 构造增强意图
        # 如果选了 archive，就把路径和你的问题揉在一起发给感知器
        final_intent = text
        if selected_arch and selected_arch != '(None)':
            final_intent = f"Analyze archive '{selected_arch}'. USER REQUEST: {text}"
        else:
            final_intent = f"USER REQUEST: {text}"

        # 3. UI 交互
        with components['chat_area']:
            ui.chat_message(text, name='You', sent=True)
            spinner = ui.spinner(size='sm')
        
        try:
            # 【关键】engine.run_once 会把 final_intent 传给 s_pcp.perceive
            # s_pcp 会返回：最新的资源地图 + 你的原始问题
            await engine.run_once(intent=final_intent)
        except Exception as e:
            ui.notify(f"System Error: {str(e)}", type='negative')
            components['thought_log'].push(f"❌ ERROR: {e}")
        finally:
            spinner.delete()

    components['send_btn'].on('click', handle_send)

if __name__ in {"__main__", "__mp_main__"}:
    main()
    ui.run(port=8080, title="AiiDA Explorer", reload=True)