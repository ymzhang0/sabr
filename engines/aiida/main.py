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
        # 获取当前选择的路径（如果是通过 Browse 按钮选择的，它也会在 archive_select 的 value 中）
        selected_arch = components['archive_select'].value
        
        if not text: return
        
        # 1. 立即清空输入，防止卡顿
        components['input'].value = ""
        
        # 2. UI 交互：立即显示用户消息
        with components['chat_area']:
            ui.chat_message(text, name='You', sent=True) \
                .classes('self-end font-medium text-white') \
                .props('bg-color=primary text-color=white')
            
            thinking_container = ui.row().classes('w-full items-center gap-3')
            with thinking_container:
                ui.spinner(size='sm', color='primary', thickness=3)
                ui.label('SABR is processing your request...').classes('text-sm text-grey-4 animate-pulse')

        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
        
        try:
            # 3. 【关键修改】：构造符合感知器正则匹配的意图字符串
            # 必须包含 "archive" 关键字并将路径用单引号包裹
            if selected_arch and selected_arch != '(None)':
                final_intent = f"Inspect archive '{selected_arch}'. User task: {text}"
            else:
                final_intent = text
            
            # 4. 调用异步 Engine
            await engine.run_once(intent=final_intent)
            
        except Exception as e:
            ui.notify(f"System Error: {str(e)}", type='negative')
        finally:
            # 5. 移除加载动画
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
