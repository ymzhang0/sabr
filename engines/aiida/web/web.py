# engines/aiida/web/web.py
from nicegui import ui

def create_layout():
    # CSS：修复气泡宽度与颜色
    ui.add_head_html('''
        <style>
            .q-message-text { max-width: 85% !important; border-radius: 18px !important; }
            .q-message-sent .q-message-text { background-color: #1a73e8 !important; color: white !important; }
            .q-message-sent .q-message-text-content { color: white !important; }
        </style>
    ''')

    # --- 1. 侧边栏 ---
    with ui.left_drawer(value=True, fixed=True).classes('bg-[#F9FBFF] border-r q-pa-lg'):
        with ui.column().classes('w-full gap-4'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('ARCHIVES').classes('text-[11px] font-bold text-blue-500 tracking-widest')
                upload_btn = ui.button(icon='add').props('flat round color=primary')
            archive_history = ui.list().props('dense').classes('w-full text-sm')
            archive_select = ui.select(options=['(None)'], value='(None)').classes('hidden')
            ui.separator()
            with ui.expansion('Insight', icon='psychology').classes('text-grey-7 text-sm'):
                # 🚩 必须创建这些变量，后续要返回
                debug_log = ui.markdown('Ready.').classes('text-[11px] p-3 bg-white border rounded-xl')
                thought_log = ui.log().classes('w-full h-40 bg-slate-900 text-slate-300 text-[10px] mt-2 rounded-xl')

    # --- 2. 锁定底部区域 (Footer) ---
    with ui.footer(fixed=True).classes('bg-white border-t flex justify-center pb-6'):
        with ui.column().classes('w-full max-w-[800px] ml-[340px] px-4 gap-2'):
            # (1) 建议卡片：位于输入框上方
            suggestion_container = ui.row().classes('w-full gap-2 no-wrap overflow-x-auto justify-center pb-2')
            suggestion_cards = []
            for label, text in [('📊 Stats', 'Show database stats'), ('🔍 Groups', 'List all groups')]:
                card = ui.card().classes('cursor-pointer p-3 min-w-[140px] shadow-none border border-blue-50 hover:bg-blue-50')
                with card: ui.label(label).classes('text-xs font-bold text-blue-800')
                suggestion_cards.append((card, text))
            # (2) 输入框
            with ui.row().classes('w-full bg-slate-100 rounded-[28px] px-6 py-1 items-center no-wrap'):
                input_field = ui.textarea(placeholder='Ask SABR...').classes('flex-grow bg-transparent').props('borderless autogrow')
                send_btn = ui.button(icon='send', color='primary').props('round flat')
            # (3) 模型选择：位于输入框下方
            with ui.row().classes('w-full items-center justify-between px-4'):
                model_select = ui.select(options=['gemini-2.0-flash', 'gemini-1.5-pro'], value='gemini-2.0-flash').props('dense borderless').classes('text-[10px] font-bold text-grey-6')
                ui.label('SABR v1.0').classes('text-[9px] text-grey-4 uppercase tracking-widest')

    # --- 3. 对话展示区 ---
    with ui.column().classes('ml-[340px] mr-12 px-8 pt-12 pb-64 flex-grow'):
        welcome_screen = ui.column().classes('items-center justify-center py-20 w-full')
        with welcome_screen: ui.label('Hi, Where should we start?').classes('text-4xl font-light text-slate-300')
        chat_area = ui.column().classes('w-full gap-6')

    # 🚩 关键修复：返回所有 main.py 和 Reporter 需要的键
    return {
        'welcome_screen': welcome_screen, 'suggestion_container': suggestion_container,
        'chat_area': chat_area, 'input': input_field, 'send_btn': send_btn,
        'upload_btn': upload_btn, 'archive_history': archive_history, 'archive_select': archive_select,
        'debug_log': debug_log, 'thought_log': thought_log, 'model_select': model_select, 
        'suggestion_cards': suggestion_cards
    }