# engines/aiida/reporters/nicegui.py
import re
from sab_core.reporters.base import BaseReporter
from nicegui import ui

class NiceGUIReporter(BaseReporter):
    def __init__(self, components):
        self.comp = components

    def _format_insight_for_human(self, raw_observation: str) -> str:
        """
        🚩 核心逻辑：清洗 Perceptor 产生的原始报告，适配侧边栏 UI。
        1. 移除冗余的 User Message 上下文
        2. 缩短长路径
        3. 图标化 Markdown 标题
        """
        # 1. 移除冗余的 "MESSAGE FROM USER" 及其内容
        # Perceptor 会自动带上用户的 Intent，这在侧边栏太占地方了
        clean_text = re.sub(r"MESSAGE FROM USER:.*?\n\n", "", raw_observation, flags=re.DOTALL)

        # 2. 路径缩短：将长路径 'C:/Users/.../data/test.aiida' 缩短为 '.../data/test.aiida'
        def shorten_path(match):
            path = match.group(1)
            # 兼容 Windows/Linux 路径斜杠
            parts = path.replace('\\', '/').split('/')
            if len(parts) > 2:
                # 仅保留最后两级：文件夹/文件名
                return f"archive '.../{'/'.join(parts[-2:])}'"
            return f"archive '{path}'"

        clean_text = re.sub(r"archive '(.+?)'", shorten_path, clean_text)

        # 3. 增强 Markdown 可读性与图标化 (替换 perceptors/database.py 中的原始标记)
        clean_text = clean_text.replace("### Source:", "📍 **Source**:")
        clean_text = clean_text.replace("- Group:", "📦 **Group**:")
        clean_text = clean_text.replace("### AIIDA RESOURCE OVERVIEW ###", "🔍 *Resource Overview*")
        
        # 4. 移除原始 YAML 风格的末尾 ### (如果有)
        clean_text = clean_text.replace("###", "").strip()

        return clean_text

    def report_system(self, event_type: str, data: dict):
        """
        实现系统上报逻辑，直接联动 Web UI 组件
        """
        if event_type == "api_status":
            status = "✅ Connected" if not data.get('error') else f"❌ Error: {data['error']}"
            self.comp['thought_log'].push(f"🌐 API Discovery: {status}")
            
            if data.get('models'):
                self.comp['model_select'].options = data['models']
                self.comp['model_select'].update()
                
                model_list = "\n".join([f"- {m}" for m in data['models'][:5]])
                self.comp['debug_log'].set_content(
                    f"### 🤖 System\n**Status**: {status}\n\n**Available Models**:\n{model_list}\n"
                )

        elif event_type == "environment_sync":
            self.comp['thought_log'].push(f"🔄 Backend Synced: {data.get('target')}")

    def emit(self, observation, action):
        """
        接收观察与决策，分发渲染到 UI
        """
        # 1. 🚩 更新 Insight 区域 (侧边栏)
        if "aiida" in observation.source:
            # 💡 调用清洗函数，不再使用 YAML 代码块包裹，以便正常显示 Markdown 图标
            formatted_content = self._format_insight_for_human(observation.raw)
            content = f"### 📊 Insight\n\n{formatted_content}"
 
            self.comp['debug_log'].set_content(formatted_content)
            
            # 2. 🚩 动态激活样式：移除透明度，增加激活类名
            self.comp['debug_log'].classes(add='insight-active opacity-100', remove='opacity-0')
            # 3. 触发一次微小的“脉冲”动效
            self.comp['debug_log'].classes(add='pill-breathing')
            ui.timer(1.0, lambda: self.comp['debug_log'].classes(remove='pill-breathing'), once=True)
        # 2. 渲染对话气泡
        if action.name == "say":
            self._render_chat_message(action.payload.get("content", ""), is_ai=True)
            self.comp['thought_log'].push(f"Decision: Sent response to user.")
        
        elif action.name == "error_reported":
            self.comp['thought_log'].push(f"⚠️ Brain Error: {action.payload.get('message')}")

    def _render_chat_message(self, content, is_ai=True):
        """
        在聊天区渲染 Markdown 消息气泡
        """
        with self.comp['chat_area']:
            if is_ai:
                with ui.row().classes('w-full items-start gap-2 mb-4'):
                    ui.avatar(icon='auto_awesome', color='primary').props('size=sm')
                    with ui.column().classes('max-w-2xl'):
                        with ui.card().classes('bg-white shadow-sm border-none p-4 rounded-2xl'):
                            # 渲染 AI 回复
                            ui.markdown(content).classes('text-md text-grey-9')

    def debug(self, message: str, level: str = "INFO"):
        # 🚩 核心：直接推送到侧边栏那个黑色的 thought_log 区域
        icon = "🛠️" if level == "DEBUG" else "ℹ️"
        self.comp['thought_log'].push(f"{icon} {message}")