import os
from nicegui import ui

from .themes import THEMES

def create_aiida_layout(theme_name='gemini_dark', available_models=["gemini-2.0-flash", "gemini-1.5-pro"]):
    """
    Standardized AiiDA Layout for SABR v2.
    Fully restores original UI elements including themes, terminal styles, and animations.
    """
    theme = THEMES.get(theme_name, THEMES['gemini_dark'])
    theme_css = ":root {\n" + "\n".join([f"    {k}: {v};" for k, v in theme.items()]) + "\n}"

    ui.add_head_html(f'''
        <link rel="stylesheet" href="/aiida/static/style.css?v={os.urandom(4).hex()}">
        <style>{theme_css}</style>
        <script>
            function inspectNode(nodeId) {{
                emitEvent('node_clicked', {{id: nodeId}});
            }}
        </script>
    ''')

    ICON_W = "w-[40px]"

    # --- 1. Sidebar (Left Drawer) ---
    with ui.left_drawer(value=True, fixed=True).props('width=380').classes('q-pa-none border-r'):
        with ui.column().classes('w-full h-full no-wrap gap-0'):
            
            # [Section 1] Branding
            with ui.row().classes('items-center px-4 py-8 gap-0'):
                with ui.element('div').classes(f'{ICON_W} flex items-center'):
                    ui.icon('auto_awesome', color='primary', size='28px')
                ui.label('SABR-AiiDA').classes('text-2xl font-black tracking-tighter')

            # [Section 2] Recent Archives
            with ui.column().classes('w-full gap-2 mb-4'):
                with ui.row().classes('w-full items-center px-4 justify-between'):
                    with ui.row().classes('items-center gap-0'):
                        with ui.element('div').classes(f'{ICON_W} flex items-center'):
                            ui.icon('history', size='18px').classes('text-slate-400')
                        ui.label('RECENT ARCHIVES').classes('text-[11px] font-bold tracking-widest text-slate-400')
                    upload_btn = ui.button(icon='add').props('flat round color=primary size=sm')
                
                with ui.column().classes('w-full max-h-[120px] h-auto overflow-y-auto px-0'):
                    archive_history = ui.list().props('dense').classes('w-full p-0')
                archive_select = ui.select(options=['(None)'], value='(None)').classes('hidden')

            ui.separator().classes('opacity-10 my-4 mx-8')

            # [Section 3] Insight & Terminal
            async def toggle_log():
                log_container.visible = not log_container.visible
                if log_container.visible:
                    terminal_header.classes(remove='rounded-xl', add='rounded-t-xl')
                    await ui.run_javascript(f'const log = document.getElementById("c{thought_log.id}"); if(log) log.scrollTop = log.scrollHeight;', respond=False)
                else:
                    terminal_header.classes(remove='rounded-t-xl', add='rounded-xl')

            with ui.expansion('', value=True).classes('w-full text-slate-400').props('header-class="px-4 py-2"') as insight_exp:
                with insight_exp.add_slot('header'):
                    with ui.row().classes('items-center w-full gap-0'):
                        with ui.element('div').classes(f'{ICON_W} flex items-center'):
                            ui.icon('analytics', size='18px')
                        ui.label('INSIGHT').classes('text-[11px] font-bold tracking-widest')

                with ui.column().classes('w-full gap-0 px-0 pb-4'):
                    # Data Insight View
                    insight_view = ui.markdown('').classes(
                        'w-full px-4 py-3 text-[12px] text-slate-200 leading-relaxed '
                        'bg-primary/5 rounded-xl border border-primary/20 mb-3 mx-0 '
                        'shadow-[inset_0_0_20px_rgba(var(--primary-rgb),0.05)]'
                    ).style('display: none;')

                    # Terminal Header
                    with ui.row().on('click', toggle_log).classes(
                            'w-full bg-[#1e1e1e] px-4 py-2 rounded-t-xl border border-white/5 '
                            'items-center cursor-pointer hover:bg-[#252525] transition-all'
                        ) as terminal_header:
                        with ui.row().classes('items-center gap-1.5 w-9 no-wrap'):
                            ui.element('div').classes('w-2.5 h-2.5 rounded-full bg-[#ff5f56]')
                            ui.element('div').classes('w-2.5 h-2.5 rounded-full bg-[#ffbd2e]')
                            ui.element('div').classes('w-2.5 h-2.5 rounded-full bg-[#27c93f]')
                        ui.label('TERMINAL').classes('text-[9px] font-black tracking-[0.2em] text-white/30 uppercase')
                        ui.space()
                        with ui.row().classes('opacity-20'):
                            icon_less = ui.icon('expand_less', size='16px')
                            icon_more = ui.icon('expand_more', size='16px')

                    # Terminal Body
                    with ui.column().classes('w-full') as log_container:
                        thought_log = ui.log().classes(
                            'thought-log-container w-full h-50 text-[10px] p-3 '
                            'bg-[#0a0a0a] rounded-b-xl border-x border-b border-white/5 '
                            'font-mono leading-relaxed'
                        )

                    icon_less.bind_visibility_from(log_container, 'visible')
                    icon_more.bind_visibility_from(log_container, 'visible', backward=lambda v: not v)

            ui.separator().classes('opacity-10 my-4 mx-8')

            # [Section 4] Live Processes
            with ui.column().classes('w-full gap-2 mb-8'):
                with ui.row().classes('items-center px-4 gap-0'):
                    with ui.element('div').classes(f'{ICON_W} flex items-center'):
                        ui.icon('sensors', size='18px').classes('text-slate-400')
                    ui.label('LIVE PROCESSES').classes('text-[11px] font-bold text-slate-400 tracking-widest')
                process_ticker = ui.column().classes('w-full px-8 gap-2')

    # --- 2. Chat Container ---
    with ui.column().classes('chat-container flex-grow w-full pb-64 items-center'):
        with ui.column().classes('w-full items-center justify-start pt-[20vh] flex-grow') as welcome_screen:
            welcome_title = ui.label('Hi, Where should we start?').classes('text-5xl font-light opacity-20 tracking-tight text-center')
            welcome_sub = ui.label('Select a shortcut or analyze your database below.').classes('text-sm text-slate-300 mt-4 uppercase tracking-widest text-center')
        
        chat_area = ui.column().classes('w-full max-w-[850px] mx-auto gap-8 px-4')

    # --- 3. Floating Footer ---
    with ui.column().classes('fixed bottom-0 right-0 z-10 p-8 items-center').style(f'left: 340px; background: linear-gradient(to top, var(--main-bg) 60%, transparent);'):
        with ui.column().classes('w-full max-w-[850px] gap-4'):
            
            # Suggestion Grid
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

            # Input Pill
            with ui.row().classes('w-full input-pill px-6 py-1 items-center no-wrap shadow-2xl') as input_container:
                input_field = ui.textarea(placeholder='Ask SABR...').classes('flex-grow bg-transparent text-xl').props('borderless autogrow')
                send_btn = ui.button(icon='send', color='primary').props('round flat size=lg')

            # Status Bar
            with ui.row().classes('w-full items-center justify-between'):
                model_select = ui.select(options=available_models, value=available_models[0]).props(
                    'flat dense borderless options-dense hide-dropdown-icon '
                    'popup-content-class="rounded-xl border border-white/10 shadow-xl"'
                ).classes('text-[12px] font-bold tracking-widest uppercase px-3 py-1 rounded-full cursor-pointer text-slate-400 hover:text-primary transition-all w-auto min-w-[120px]')
                
                with model_select.add_slot('prepend'):
                    with ui.element('div').classes('flex items-center justify-center pr-2'):
                        ui.element('div').classes('w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]')
                
                ui.label('AI ENGINE READY').classes('text-[9px] font-black tracking-widest text-primary/40')
                ui.label('LATENCY: STABLE').classes('text-[9px] font-black opacity-30 tracking-widest')

    return {
        'welcome_screen': welcome_screen, 
        'welcome_title': welcome_title, 
        'welcome_sub': welcome_sub, 
        'suggestion_container': suggestion_container,
        'chat_area': chat_area, 
        'input_container': input_container, 
        'input': input_field, 
        'send_btn': send_btn,
        'upload_btn': upload_btn, 
        'archive_history': archive_history, 
        'archive_select': archive_select,
        'insight_view': insight_view, 
        'thought_log': thought_log, 
        'model_select': model_select, 
        'suggestion_cards': suggestion_cards,
        'process_ticker': process_ticker
    }
