from nicegui import ui
from engines.aiida.web.themes import THEMES

def create_layout(theme_name='oxford'):
    theme = THEMES.get(theme_name, THEMES['oxford'])
    theme_css = ":root {\n" + "\n".join([f"    {k}: {v};" for k, v in theme.items()]) + "\n}"

    ui.add_head_html(f'''
        <link rel="stylesheet" href="/aiida/static/style.css?v=1">
        <style>
            {theme_css}
        </style>
    ''')
    # ...

    # --- 1. 侧边栏 ---
    with ui.left_drawer(value=True, fixed=True).props('width=340').classes('q-pa-none') as drawer:
        with ui.column().classes('w-full h-full no-wrap gap-0'):
            with ui.row().classes('items-center gap-3 px-6 py-8'):
                ui.icon('auto_awesome', color='primary', size='32px')
                ui.label('SABR-AiiDA').classes('text-2xl font-bold tracking-tighter')
            
            with ui.column().classes('history-container w-full flex-grow gap-2 px-6'):
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('RECENT ARCHIVES').classes('text-[11px] font-bold tracking-widest text-slate-400')
                    upload_btn = ui.button(icon='add').props('flat round color=primary size=sm')
                with ui.scroll_area().classes('w-full flex-grow'):
                    archive_history = ui.list().props('dense').classes('w-full')
                archive_select = ui.select(options=['(None)'], value='(None)').classes('hidden')

            ui.separator().classes('opacity-10 my-4')
            with ui.expansion('ENGINE INSIGHT', icon='analytics', value=True).classes('w-full px-6 text-slate-400'):
                with ui.column().classes('w-full gap-2 pb-8'):
                    debug_log = ui.markdown('Ready.').classes('insight-markdown text-[11px] p-4')
                    thought_log = ui.log().classes('w-full h-32 text-[10px] p-2 bg-black rounded-xl mt-2')

    # --- 2. 核心对话区 ---
    with ui.column().classes('chat-container flex-grow w-full pb-64') as main_column:
        with ui.column().classes('items-center justify-center py-24 w-full') as welcome_screen:
            ui.label('Hi, Where should we start?').classes('text-5xl font-light opacity-20 tracking-tight')
        chat_area = ui.column().classes('w-full max-w-[900px] mx-auto gap-8 px-4')

    # --- 3. 悬浮控制区 (Fixed Footer) ---
    with ui.column().classes('fixed bottom-0 right-0 p-8 z-10') \
            .style(f'left: 340px; background: linear-gradient(to top, var(--main-bg) 60%, transparent);'):
        
        with ui.column().classes('w-full max-w-[1000px] mx-auto'):
            # 🚩 重点：确保使用 div + suggestion-grid 类名
            with ui.element('div').classes('suggestion-grid') as suggestion_container:
                suggestion_cards = []
                prompts = [
                    ('📊 DB Statistics', 'Overview of nodes', 'Show me the statistics of current database'),
                    ('🔍 Group Explorer', 'Identify user groups', 'List all groups in this archive'),
                    ('⚡ Recent Activity', 'Last 5 successful tasks', 'What are the last 5 successful processes?'),
                    ('🛠️ PW Relax', 'Draft QE WorkChain', 'Help me draft a PW relax workchain')
                ]
                for title, subtitle, full_intent in prompts:
                    card = ui.card().classes('suggestion-card cursor-pointer shadow-none')
                    with card:
                        with ui.column().classes('gap-1'):
                            ui.label(title).classes('text-lg font-bold')
                            ui.label(subtitle).classes('text-xs opacity-50')
                    suggestion_cards.append((card, full_intent))

            # 输入框
            with ui.row().classes('w-full input-pill px-8 py-3 items-center no-wrap shadow-lg'):
                input_field = ui.textarea(placeholder='Ask SABR...').classes('flex-grow bg-transparent text-xl').props('borderless autogrow')
                send_btn = ui.button(icon='send', color='primary').props('round flat size=lg')

            with ui.row().classes('w-full items-center justify-between px-6 opacity-40'):
                model_select = ui.select(options=['gemini-2.0-flash'], value='gemini-2.0-flash').props('dense borderless').classes('text-[10px] font-bold')
                ui.label('SABR-AiiDA v1.2').classes('text-[9px] uppercase tracking-widest')

    return {
        'welcome_screen': welcome_screen, 'suggestion_container': suggestion_container,
        'chat_area': chat_area, 'input': input_field, 'send_btn': send_btn,
        'upload_btn': upload_btn, 'archive_history': archive_history, 'archive_select': archive_select,
        'debug_log': debug_log, 'thought_log': thought_log, 'model_select': model_select, 
        'suggestion_cards': suggestion_cards
    }