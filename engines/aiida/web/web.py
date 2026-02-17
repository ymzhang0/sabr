# engines/aiida/web/web.py
from nicegui import ui

def create_layout():
    # 🎨 CSS 增强
    ui.add_head_html('''
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
            body { background-color: #FFFFFF; font-family: 'Inter', sans-serif; overflow-x: hidden; }
            
            /* 🚩 气泡宽度：占满容器且与输入框对齐 */
            .q-message-text { 
                max-width: 100% !important; 
                width: auto !important; 
                min-width: 200px;
                border-radius: 20px !important; 
                padding: 12px 18px !important;
                font-size: 14px !important;
                line-height: 1.5;
            }
            .q-message-container { width: 100% !important; margin-bottom: 12px; }
            
            /* 🚩 确保发送消息清晰可见 (深蓝色 + 纯白文字) */
            .q-message-sent .q-message-text { 
                background-color: #1a73e8 !important; 
                color: white !important; 
            }
            .q-message-sent .q-message-text-content { color: white !important; }
            
            .q-message-received .q-message-text { background-color: #f1f3f4 !important; color: #3c4043 !important; }
            .custom-input .q-field__control { min-height: 64px !important; border-radius: 32px !important; }
        </style>
    ''')

    # --- 1. 侧边栏 ---
    with ui.left_drawer(value=True, fixed=True).classes('bg-[#F9FBFF] border-r q-pa-lg'):
        with ui.column().classes('w-full gap-6'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('ARCHIVES').classes('text-[11px] font-bold text-blue-500 tracking-widest')
                # 🚩 确认 icon 为 'add'
                upload_btn = ui.button(icon='add').props('flat round color=primary').tooltip('Upload Archive')
            
            archive_history = ui.list().props('dense').classes('w-full text-sm')
            archive_select = ui.select(options=['(None)'], value='(None)').classes('hidden')
            
            ui.separator()
            with ui.expansion('Engine Insight', icon='psychology').classes('text-grey-7 text-sm'):
                debug_log = ui.markdown('Ready.').classes('text-[11px] p-3 bg-white border rounded-xl')
                thought_log = ui.log().classes('w-full h-40 bg-slate-900 text-slate-300 text-[10px] mt-2 rounded-xl')

    # --- 底部固定区 ---
    with ui.footer(fixed=True).classes('bg-white border-t flex justify-center pb-6'):
        # 限制最大宽度并居中，左侧留出 Drawer 的宽度 (340px)
        with ui.column().classes('w-full max-w-[900px] ml-[340px] px-4 gap-2'):
            
            # 1. 快捷建议 (Suggestions) - 放在输入框上方
            suggestion_container = ui.row().classes('w-full gap-2 no-wrap overflow-x-auto pb-2 justify-center')
            suggestion_cards = []
            prompts = [('📊 Stats', 'Show stats'), ('🔍 Groups', 'List groups')]
            for label, text in prompts:
                card = ui.card().classes('cursor-pointer p-3 min-w-[140px] shadow-none border border-blue-100 hover:bg-blue-50')
                with card:
                    ui.label(label).classes('text-xs font-bold text-blue-800')
                suggestion_cards.append((card, text))

            # 2. 对话输入框 (Locked Position)
            with ui.row().classes('w-full bg-slate-50 rounded-[24px] px-6 py-2 items-center no-wrap border'):
                input_field = ui.textarea(placeholder='Ask SABR...').classes('flex-grow bg-transparent').props('borderless autogrow')
                send_btn = ui.button(icon='send', color='primary').props('round flat')

            # 3. 🚩 模式选择 (放在对话框正下方)
            with ui.row().classes('w-full items-center justify-between px-4'):
                with ui.row().classes('items-center gap-1'):
                    ui.icon('settings', size='12px', color='grey-5')
                    model_select = ui.select(
                        options=['gemini-2.0-flash', 'gemini-1.5-pro'],
                        value='gemini-2.0-flash'
                    ).props('dense borderless').classes('text-[10px] font-bold text-grey-6')
                ui.label('SABR-AiiDA v1.0').classes('text-[9px] text-grey-4 uppercase tracking-widest')

    # --- 对话显示区 ---
    with ui.column().classes('w-full max-w-[900px] ml-[340px] px-8 pt-12 pb-64'):
        welcome_screen = ui.column().classes('items-center justify-center py-20 w-full')
        with welcome_screen:
            ui.label('Hi, Where should we start?').classes('text-4xl font-light text-slate-400')
        chat_area = ui.column().classes('w-full gap-6')

    return {
        'welcome_screen': welcome_screen, 'suggestion_container': suggestion_container,
        'chat_area': chat_area, 'input': input_field, 'send_btn': send_btn,
        'upload_btn': upload_btn, 'archive_history': archive_history, 'archive_select': archive_select,
        'debug_log': debug_log, 'thought_log': thought_log, 'suggestion_cards': suggestion_cards, 'model_select': model_select,
    }