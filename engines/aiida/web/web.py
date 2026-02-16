from nicegui import ui
from engines.aiida.tools.profile import list_local_archives

def create_layout():
    """创建三栏布局：资源、对话、调试"""
    with ui.row().classes('w-full h-[90vh] no-wrap'):
        # 1. 左侧资源浏览器
        with ui.column().classes('col-2 border-r q-pa-sm bg-grey-2'):
            ui.label('📁 ARCHIVES').classes('text-bold text-xs mb-2')
            archive_select = ui.select(
                options=['(None)'] + list_local_archives(),
                label='Target Archive',
                value='(None)'
            ).classes('w-full')
            ui.button('Refresh', on_click=lambda: archive_select.set_options(['(None)'] + list_local_archives())).props('flat dense icon=refresh size=sm')

        # 2. 中间对话区
        with ui.column().classes('col-6 h-full q-pa-md'):
            chat_area = ui.scroll_area().classes('w-full flex-grow border bg-grey-1 q-pa-sm')
            with ui.row().classes('w-full items-end'):
                input_field = ui.textarea(label='Command', placeholder='What would you like to do?').classes('flex-grow')
                send_btn = ui.button(icon='send').props('round elevated lg')

        # 3. 右侧调试面板
        with ui.column().classes('col-4 h-full q-pa-md bg-blue-grey-1'):
            ui.label('📡 SCHEMA MAP').classes('text-bold text-xs')
            debug_log = ui.code('', language='text').classes('w-full h-1/2 bg-white border')
            ui.label('🔬 BRAIN LOGS').classes('text-bold text-xs q-mt-md')
            thought_log = ui.log().classes('w-full h-1/2 bg-black text-green-2 text-xs')

    return {
        'chat_area': chat_area, 'input': input_field, 'send_btn': send_btn,
        'debug_log': debug_log, 'thought_log': thought_log, 'archive_select': archive_select
    }