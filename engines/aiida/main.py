import os

from nicegui import ui, run
import tkinter as tk
from tkinter import filedialog

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

    # --- 1. 档案切换逻辑 ---
    async def select_archive(path):
        """同步 UI 状态并强制后端感知器刷新 Profile"""
        components['archive_select'].value = path
        ui.notify(f"Switched to: {os.path.basename(path)}", color='primary')
        # 🚩 触发一次静默运行，强制 Perceptor 执行 load_profile
        await engine.run_once(intent=f"Inspect archive '{path}'. User task: System Refresh")

    # --- 2. 文件上传逻辑 (带错误捕获和置顶保护) ---
    async def pick_local_file():
        def get_path():
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            path = filedialog.askopenfilename(filetypes=[("AiiDA Archives", "*.aiida *.zip")])
            root.destroy()
            return path

        selected_path = await run.io_bound(get_path)
        if selected_path:
            if selected_path not in components['archive_select'].options:
                components['archive_select'].options.append(selected_path)
                with components['archive_history']:
                    # 🚩 使用 with 语句正确添加 Item
                    with ui.item(on_click=lambda p=selected_path: components['archive_select'].set_value(p)) \
                        .classes('rounded-xl hover:bg-blue-50 px-3 cursor-pointer'):
                        with ui.item_section():
                            ui.label(os.path.basename(selected_path)).classes('text-xs')
            
            components['archive_select'].value = selected_path

    components['upload_btn'].on('click', pick_local_file)

# 1. 修正模型切换事件 (解决特性消失问题)
    def handle_model_change(e):
        engine._brain._model_name = e.value
        ui.notify(f"Brain active: {e.value}")
    components['model_select'].on_value_change(handle_model_change)
    
    # 3. 发送逻辑 (带引导隐藏)
    async def handle_send(preset_text=None):
        text = preset_text if preset_text else components['input'].value
        if not text: return
        
        components['welcome_screen'].set_visibility(False)
        components['suggestion_container'].set_visibility(False)
        components['input'].value = ""

        with components['chat_area']:
            ui.chat_message(text, name='You', sent=True).classes('self-end w-full')
            
            thinking = ui.row().classes('items-center gap-2 pl-4')
            with thinking:
                ui.spinner(size='xs'); ui.label('Processing...').classes('text-xs text-grey-5')

        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
        
        try:
            arch = components['archive_select'].value
            intent = f"Inspect archive '{arch}'. User task: {text}" if arch != '(None)' else text
            await engine.run_once(intent=intent)
        finally:
            thinking.delete()

    components['send_btn'].on('click', lambda: handle_send())
    
    # 🚩 绑定建议卡片点击直接发送
    for card, full_text in components['suggestion_cards']:
        card.on('click', lambda t=full_text: handle_send(t))

    ui.run(
        port=8080, 
        title="SABR-AiiDA Explorer", 
        reload=False,   # 🚩 Windows 下 reload=True 极易导致进程卡死，建议关闭
        dark=False, 
        show=True       # 自动打开浏览器，省得你手动点
    )

if __name__ in {"__main__", "__mp_main__"}:
    main()
