from sab_core.reporters.base import BaseReporter
from nicegui import ui

class NiceGUIReporter(BaseReporter):
    def __init__(self, components):
        self.comp = components

    def emit(self, observation, action):
        # 更新 Schema 地图 (侧边栏)
        if "aiida" in observation.source:
            # 使用更清爽的渲染方式
            self.comp['debug_log'].set_content(f"```yaml\n{observation.raw}\n```")

        # 记录内部思考 (Console 风格)
        self.comp['thought_log'].push(f"Decision: {action.name}")

        # 渲染 AI 回复
        if action.name == "say":
            content = action.payload.get("content", "")
            with self.comp['chat_area']:
                with ui.row().classes('w-full items-start gap-2 mb-4'):
                    ui.avatar(icon='auto_awesome', color='primary').props('size=sm')
                    with ui.column().classes('max-w-2xl'):
                        # 气泡容器
                        with ui.card().classes('bg-white shadow-sm border-none p-4 rounded-2xl'):
                            ui.markdown(content).classes('text-md text-grey-9')
        
        # 如果是工具调用，也给个视觉反馈
        elif action.name != "no_op":
            self.comp['thought_log'].push(f"🛠️ Tool Call: {action.name}({action.payload})")