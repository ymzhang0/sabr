# engines/aiida/reporters/nicegui.py
from sab_core.reporters.base import BaseReporter
from nicegui import ui

class NiceGUIReporter(BaseReporter):
    def __init__(self, components):
        self.comp = components

    def report_system(self, event_type: str, data: dict):
        """
        🚩 实现系统上报逻辑，直接联动 Web UI 组件
        """
        if event_type == "api_status":
            # 在 Insight 区域顶部插入 API 状态
            status = "✅ Connected" if not data.get('error') else f"❌ Error: {data['error']}"
            self.comp['thought_log'].push(f"🌐 API Discovery: {status}")
            
            if data.get('models'):
                # 🚩 增加这一行：确保报告器也能更新下拉框组件
                self.comp['model_select'].options = data['models']
                self.comp['model_select'].update()
                
                # 动态生成模型列表并更新到 Insight
                model_list = "\n".join([f"- {m}" for m in data['models'][:5]]) # 仅显示前5个
                self.comp['debug_log'].set_content(
                    f"### 🤖 System\n**Status**: {status}\n\n**Available Models**:\n{model_list}\n"
                )

        elif event_type == "environment_sync":
            # 当 AiiDA Profile 切换成功时，在日志中闪烁提醒
            self.comp['thought_log'].push(f"🔄 Backend Synced: {data.get('target')}")

    def emit(self, observation, action):
        # 1. 更新 Insight 区域 (侧边栏)
        if "aiida" in observation.source:
            # 将原始观察报告包裹在代码块中，防止 Markdown 渲染冲突
            content = f"### 📊 Latest Observation\n```yaml\n{observation.raw}\n```"
            self.comp['debug_log'].set_content(content)

        # 2. 渲染对话气泡 (保持你优雅的渲染逻辑)
        if action.name == "say":
            self._render_chat_message(action.payload.get("content", ""), is_ai=True)
            self.comp['thought_log'].push(f"Decision: Sent response to user.")
        
        elif action.name == "error_reported":
            # 如果是决策过程报错，直接显示在 Insight 区
            self.comp['thought_log'].push(f"⚠️ Brain Error: {action.payload.get('message')}")

    def _render_chat_message(self, content, is_ai=True):
        with self.comp['chat_area']:
            if is_ai:
                with ui.row().classes('w-full items-start gap-2 mb-4'):
                    ui.avatar(icon='auto_awesome', color='primary').props('size=sm')
                    with ui.column().classes('max-w-2xl'):
                        with ui.card().classes('bg-white shadow-sm border-none p-4 rounded-2xl'):
                            ui.markdown(content).classes('text-md text-grey-9')