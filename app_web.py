# app_web.py
from nicegui import ui, app
from src.sab_core.factory import load_ui_package
from src.sab_core.config import settings

@ui.page('/')
async def main():
    # 1. 动态获取当前引擎的“UI 生产线”
    create_layout, ControllerClass = load_ui_package()
    
    # 2. 生成 UI
    components = create_layout()
    
    # 3. 实例化控制器
    ctrl = ControllerClass(api_url=settings.API_URL, components=components)
    await ctrl.initialize()

    # 4. 绑定基础事件
    components['send_btn'].on('click', lambda: ctrl.handle_send())
    components['input'].on('keydown.enter', lambda: ctrl.handle_send())
    
    if 'archive_select' in components:
        components['archive_select'].on_value_change(lambda e: ctrl.switch_context(e.value))

    app.on_shutdown(ctrl.close)

ui.run(port=8080)