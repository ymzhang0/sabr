# engines/aiida/ui/layout.py
from nicegui import ui

def create_layout():
    """
    这个函数只负责画图，不负责任何 AiiDA 的后端计算。
    它只依赖 nicegui。
    """
    with ui.header().classes('bg-slate-900 p-4'):
        ui.label('SABR x AiiDA Expert').classes('text-xl font-bold')
        
    with ui.column().classes('w-full max-w-4xl mx-auto p-4'):
        # 即使是 AiiDA 专用的档案选择器，我们也只画一个下拉框
        # 实际的数据填充通过 app_web.py 调用 API 完成
        archive_select = ui.select(label='AiiDA Archive', options=[]).classes('w-full')
        chat_area = ui.column().classes('w-full border p-4 rounded-xl h-96 overflow-auto')
        user_input = ui.input(placeholder='Ask AiiDA expert...').classes('w-full')
        send_btn = ui.button('Execute', icon='bolt')

    return {
        'archive_select': archive_select,
        'chat_area': chat_area,
        'input': user_input,
        'send_btn': send_btn
    }