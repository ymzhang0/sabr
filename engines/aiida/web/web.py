from nicegui import ui, run
import os
from engines.aiida.tools.profile import list_local_archives
from tkinter import filedialog, Tk
def create_layout():
    # 🎨 注入全局 CSS 魔法：解决气泡自适应、滚动条和布局间距
    ui.add_head_html('''
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
            body { background-color: #FFFFFF; font-family: 'Inter', sans-serif; }
            /* 气泡自适应宽度 */
            .q-message-text { max-width: 85% !important; width: auto !important; border-radius: 18px !important; }
            .q-message-container { width: 100% !important; }
            /* 输入框呼吸感 */
            .custom-input .q-field__control { height: 80px !important; padding: 10px 20px !important; }
            /* 侧边栏干净风格 */
            .q-drawer { background-color: #F9FBFF !important; }
            .q-item__section--side { color: #606266; }
        </style>
    ''')

    # --- 1. 头部 ---
    with ui.header(elevated=False).classes('bg-white text-grey-9 q-pa-md border-b'):
        with ui.row().classes('w-full items-center no-wrap'):
            ui.icon('bolt', color='primary').classes('text-2xl')
            ui.label('SABR').classes('text-xl font-bold tracking-tighter')
            ui.badge('AiiDA v2.6', color='blue-1 text-blue-8').props('outline').classes('ml-2')

    # --- 2. 侧边栏 (配色与右侧统一) ---
    with ui.left_drawer(value=True, fixed=True).classes('q-pa-lg border-r'):
        with ui.column().classes('w-full gap-6'):
            ui.label('Data Resources').classes('text-xs font-bold text-blue-5 tracking-widest uppercase')
            
            # 选择器：显示已选路径
            archive_select = ui.select(
                options=['(None)'] + list_local_archives(),
                label='Selected Resource',
                value='(None)'
            ).classes('w-full').props('outlined rounded bg-white dense')

            # 🆕 本地浏览按钮：核心功能
            async def pick_local_file():
                # 在 io_bound 中运行，防止阻塞 NiceGUI 事件循环
                def get_path():
                    root = Tk()
                    root.withdraw()
                    root.attributes('-topmost', True) # 确保窗口在最前面
                    file_path = filedialog.askopenfilename(filetypes=[("AiiDA Archives", "*.aiida *.zip")])
                    root.destroy()
                    return file_path

                selected_path = await run.io_bound(get_path)
                if selected_path:
                    # 将绝对路径加入选项并选中，这样 Perceptor 就能拿到完整路径
                    if selected_path not in archive_select.options:
                        archive_select.options.append(selected_path)
                    archive_select.value = selected_path
                    ui.notify(f'Selected: {os.path.basename(selected_path)}')

            ui.button('Browse Computer', icon='folder', on_click=pick_local_file) \
                .props('unelevated rounded color=primary').classes('w-full py-2')

            ui.separator().classes('q-my-sm')

            # 🆕 增加复制按钮的 Insight 区域
            with ui.row().classes('w-full items-center no-wrap'):
                with ui.expansion('Insight', icon='psychology').classes('flex-grow text-grey-6 text-sm'):
                    debug_log = ui.markdown('System standby.').classes('text-[11px] p-3 bg-white rounded-xl border')
                    thought_log = ui.log().classes('w-full h-48 bg-slate-900 text-slate-300 text-[10px] mt-2 rounded-xl')
                
                # 点击复制按钮：将 markdown 内容写进剪贴板
                ui.button(icon='content_copy', 
                          on_click=lambda: ui.run_javascript(f'navigator.clipboard.writeText({repr(debug_log.content)})')) \
                    .props('flat round dense color=grey-4') \
                    .tooltip('Copy insights')

    # --- 3. 底部区域 (Gemini 风格布局) ---
    with ui.footer(fixed=True).classes('bg-transparent border-none flex justify-start pb-10'):
        # 这里的 ml-[340px] 确保了不挤占侧边栏空间
        with ui.column().classes('w-full max-w-none ml-[340px] mr-12 gap-2'):
            
            # 第一行：输入框 (Pill Shape)
            with ui.row().classes('w-full bg-white shadow-2xl rounded-[32px] px-8 py-4 border-2 border-blue-50 items-center no-wrap'):
                input_field = ui.textarea(placeholder='Describe the analysis...').classes('flex-grow custom-input').props('borderless autogrow')
                with ui.row().classes('items-center gap-2'):
                    ui.button(icon='attach_file').props('flat round color=grey-4')
                    send_btn = ui.button(icon='auto_awesome', color='primary').props('round elevated size=lg')

            # 🆕 第二行：模型选择与其他辅助信息 (放在输入框下方)
            with ui.row().classes('items-center gap-4 ml-6'):
                with ui.row().classes('items-center gap-1 cursor-pointer'):
                    ui.icon('auto_awesome', color='primary').classes('text-[10px]')
                    model_select = ui.select(
                        options=[
                            'gemini-2.0-flash', 
                            'gemini-2.0-pro-exp-02-05', 
                            'gemini-1.5-pro'
                        ],
                        value='gemini-2.0-flash'
                    ).props('dense options-dense borderless').classes('text-[11px] font-bold text-grey-5 bg-transparent')
                
                # 装饰性标签或状态
                ui.label('SABR V1.0').classes('text-[9px] text-grey-4 uppercase tracking-widest ml-2')
    # --- 4. 主对话区 (同步修正间距) ---
    # 🚀 关键修改：ml-[340px] 确保与输入框对齐，且不被侧边栏遮挡
    with ui.column().classes('w-full max-w-none ml-[340px] mr-12 q-pa-lg mb-40'):
        chat_area = ui.column().classes('w-full gap-8 items-start') 

    return {
        'chat_area': chat_area, 
        'input': input_field, 
        'send_btn': send_btn,
        'debug_log': debug_log, 
        'thought_log': thought_log, 
        'archive_select': archive_select,
        'model_select': model_select  # 🚩 记得返回这个组件
    }