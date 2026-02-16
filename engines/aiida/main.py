from nicegui import ui
from sab_core.engine import SABEngine
from sab_core.reporters.console import ConsoleReporter
from engines.aiida.perceptors.database import AIIDASchemaPerceptor
from engines.aiida.perceptors.human import HumanPerceptor
from engines.aiida.brain_factory import create_aiida_brain
from engines.aiida.web.web import create_layout
from engines.aiida.reporters.nicegui import NiceGUIReporter
from engines.aiida.executors.executor import AiiDAExecutor 

def main():

    ui.add_head_html('''
        <style>
            .nicegui-chat-message { margin-bottom: 20px; }
            .q-message-text { border-radius: 18px !important; }
            /* 模仿 Gemini 的输入框阴影 */
            .q-field--outlined .q-field__control {
                border-radius: 28px !important;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08) !important;
                border: 1px solid #eee !important;
            }
        </style>
    ''')

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
        
        components['input'].value = ""
        
        # UI 交互
        with components['chat_area']:
            # 🆕 用户气泡：使用 fit-content 逻辑
            ui.chat_message(text, name='You', sent=True) \
                .classes('self-end font-medium text-white') \
                .props('bg-color=primary text-color=white')
            
            thinking_container = ui.row().classes('w-full items-center gap-3')
            with thinking_container:
                ui.spinner(size='sm', color='primary', thickness=3)
                ui.label('SABR is processing your request...').classes('text-sm text-grey-4 animate-pulse')

        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
        
        try:
            final_intent = f"Using {selected_arch}: {text}" if selected_arch != '(None)' else text
            await engine.run_once(intent=final_intent)
        except Exception as e:
            ui.notify(f"System Error: {str(e)}", type='negative')
        finally:
            thinking_container.delete()

    components['send_btn'].on('click', handle_send)

    ui.run(
        port=8080, 
        title="SABR-AiiDA Explorer", 
        reload=False,   # 🚩 Windows 下 reload=True 极易导致进程卡死，建议关闭
        dark=False, 
        show=True       # 自动打开浏览器，省得你手动点
    )

if __name__ in {"__main__", "__mp_main__"}:
    main()
