from nicegui import ui
import os
from engines.aiida.tools.profile import list_local_archives

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
    with ui.left_drawer(value=True, fixed=True).classes('q-pa-lg border-r') as drawer:
        with ui.column().classes('w-full gap-6'):
            # 标题部分
            with ui.column().classes('gap-1'):
                ui.label('Data Resources').classes('text-xs font-bold text-blue-5 tracking-widest uppercase')
                ui.label('Select your provenance source').classes('text-xs text-grey-5')
            
            # 选择器优化
            archive_select = ui.select(
                options=['(None)'] + list_local_archives(),
                label='Target Archive',
                value='(None)'
            ).classes('w-full').props('outlined rounded bg-white color=primary')

            # 上传区改为更高级的按钮组样式
            def handle_upload(e):
                with open(e.name, 'wb') as f: f.write(e.content.read())
                ui.notify(f'Successfully imported {e.name}', color='positive')
                archive_select.set_options(['(None)'] + list_local_archives())
                archive_select.value = e.name

            with ui.card().classes('w-full bg-blue-50/30 border-dashed border-blue-200 shadow-none p-4 items-center'):
                ui.icon('cloud_upload', size='md', color='blue-4')
                ui.upload(on_upload=handle_upload, auto_upload=True) \
                    .props('flat color=primary dense').classes('w-full')
                ui.label('Drag & drop .aiida files').classes('text-[10px] text-blue-4 mt-1')

            ui.separator().classes('q-my-sm')

            # 内部日志 (隐藏得更深)
            with ui.row().classes('w-full items-center justify-between pr-2'):
                with ui.expansion('Insight', icon='psychology').classes('w-full text-grey-6 text-sm'):
                    debug_log = ui.markdown('System standby.').classes('text-[11px] p-3 bg-white rounded-xl border leading-relaxed')
                    thought_log = ui.log().classes('w-full h-48 bg-slate-900 text-slate-300 text-[10px] mt-2 rounded-xl shadow-inner')
                # 复制按钮：点击后将 debug_log 的内容复制到剪贴板
                ui.button(icon='content_copy', on_click=lambda: ui.run_javascript(f'navigator.clipboard.writeText(`{debug_log.content}`)')) \
                    .props('flat round dense color=grey-4') \
                    .tooltip('Copy insights')
    # --- 3. 底部输入框 (更高、更长) ---
    with ui.footer(fixed=True).classes('bg-transparent border-none flex justify-center pb-10'):
        # 增加 max-w-5xl 使其在右侧扩展更多空间
        with ui.row().classes('w-full max-w-5xl bg-white shadow-2xl rounded-[32px] px-8 py-4 border-2 border-blue-50 items-center no-wrap'):
            input_field = ui.textarea(placeholder='Describe the analysis you want to perform...').classes('flex-grow custom-input').props('borderless autogrow')
            
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='attach_file').props('flat round color=grey-4')
                send_btn = ui.button(icon='auto_awesome', color='primary').props('round elevated size=lg')

    # --- 4. 主对话区 (扩展宽度) ---
    # 改为 max-w-5xl 并调整对齐
    with ui.column().classes('w-full max-w-5xl mx-auto q-pa-xl mb-40'):
        chat_area = ui.column().classes('w-full gap-8 items-start') # 确保 items-start 防止强制拉伸
    
    return {
        'chat_area': chat_area, 
        'input': input_field, 
        'send_btn': send_btn,
        'debug_log': debug_log, 
        'thought_log': thought_log, 
        'archive_select': archive_select
    }