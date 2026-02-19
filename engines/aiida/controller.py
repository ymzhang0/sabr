import os
import tkinter as tk
from tkinter import filedialog
from nicegui import ui, run
from engines.aiida.tools import get_database_summary, get_recent_processes
from sab_core.protocols.controller import BaseController
from sab_core.memory.json_memory import JSONMemory
from src.sab_core.config import settings

class AiiDAController(BaseController):
    """
    AiiDA 引擎专用控制器
    实现具体的 AiiDA 数据库操作与 NiceGUI 组件的绑定
    """
    def __init__(self, engine, components, memory):
        super().__init__(engine, components)
        self.global_mem = memory
        # 🚩 启动时自动恢复历史列表
        self._load_archive_history()
        self.ticker_timer = ui.timer(10.0, self.update_process_status)
        self.terminal = components.get('thought_log')
        self.insight = components.get('insight_view')
    def _load_archive_history(self):
        """从全局记忆中读取历史路径并填充 UI"""
        history = self.global_mem.get_raw_data("recent_archives") or []
        if not history: return

        # 更新下拉框选项
        self.components['archive_select'].options = history
        
        # 更新左侧边栏的 UI 列表
        with self.components['archive_history']:
            for path in history:
                filename = os.path.basename(path)
                with ui.item(on_click=lambda p=path: self.components['archive_select'].set_value(p)) \
                    .classes('rounded-xl hover:bg-blue-50 px-8 py-1 cursor-pointer'):
                    with ui.item_section():
                        ui.label(filename).classes('text-xs')

    def _add_to_history_ui(self, path: str):
        """
        🚩 核心修复：将新选择的路径动态渲染到左侧边栏的 ui.list 中
        """
        import os
        from nicegui import ui
        
        filename = os.path.basename(path)
        
        # 使用 context manager 指向 web.py 中定义的 list 容器
        with self.components['archive_history']:
            # 🚩 优化：点击时调用专有的 handle_archive_selection
            item = ui.item(on_click=lambda: self.handle_archive_selection(path)) \
                .classes('px-8 py-2 rounded-xl cursor-pointer transition-all duration-300 '
                        'group hover:bg-white/5 hover:pl-10') # 增加一个向右滑动的动效
                
            with item:
                with ui.row().classes('items-center gap-0 w-full'):
                    # 图标占位
                    with ui.element('div').classes('w-[44px] flex items-center'):
                        # 🚩 group-hover:text-primary -> 悬停时图标变亮
                        ui.icon('insert_drive_file', size='16px') \
                            .classes('text-slate-500 transition-colors group-hover:text-primary')
                    
                    # 文件名
                    # 🚩 group-hover:text-white -> 悬停时文字从灰色变为纯白
                    ui.label(filename).classes(
                        'text-[11px] font-medium text-slate-400 transition-colors '
                        'group-hover:text-white'
                    )
    async def handle_archive_selection(self, path: str):
        """当用户点击侧边栏档案时的核心处理逻辑"""
        import os
        filename = os.path.basename(path)
        
        # 1. 更新内部状态（这会解除 Ticker 的守卫）
        self.components['archive_select'].set_value(path)
        
        # 2. UI 反馈：立即在对话框显示一条“系统提示”或 AI 回复
        self.engine.log(f"Switching environment to: {filename}", level="INFO")
        
        # 3. 构造一个伪意图，让 Engine 自动触发扫描和加载逻辑
        # 这样就不需要在 Engine 内部写死数据库操作
        switch_intent = f"Inspect archive '{path}'"
        
        # 4. 模拟用户发送，让 AI 给出专业的档案摘要
        await self.handle_send(preset_text=switch_intent)
        
        # 5. 成功后的视觉提示
        ui.notify(f"Environment switched to {filename}", color='positive', icon='check_circle')
 
    async def update_process_status(self):
        """后台任务状态条更新逻辑"""
        # 🚩 严密的守卫：确保只有在选中了有效档案时才执行查询
        current_archive = self.components['archive_select'].value
        if not current_archive or current_archive == "(None)":
            return 

        try:
            
            # 使用 io_bound 避免 AiiDA 查询导致 UI 抽搐
            processes = await run.io_bound(get_recent_processes, limit=5)
            
            # 分发给 Reporter 渲染
            for reporter in self.engine._reporters:
                if hasattr(reporter, 'render_processes'):
                    reporter.render_processes(processes)
                    
        except Exception as e:
            # 这里记录到 Thought Log，方便调试但不弹窗干扰用户
            self.engine.log(f"Ticker update skipped: {str(e)}", level="DEBUG")

    def log(self, message: str, level: str = "INFO"):
        """智能日志路由：决定信息去往终端还是见解区"""
        
        # 1. 如果信息包含 Markdown 表格或明显的结构化特征，发送到 Insight View
        if self._is_conclusive_content(message):
            self._render_insight(message)
        else:
            # 2. 否则，发送到技术终端 Terminal
            self._render_terminal(message, level)

    def _is_conclusive_content(self, message: str) -> bool:
        """识别内容是否为“结论性/结构化”数据"""
        # 检查是否包含表格、二级以上标题、或明确的结论标记
        has_table = "|" in message and "---" in message
        has_header = message.strip().startswith("##") or message.strip().startswith("###")
        is_summary = "Conclusion:" in message or "Summary:" in message
        return has_table or has_header or is_summary

    def _render_terminal(self, message: str, level: str):
        """格式化并推送到黑色终端"""
        if not self.terminal: return
        
        # 定义不同级别的颜色（ANSI 风格或简单的 Emoji）
        icons = {
            "INFO": "🔹",
            "DEBUG": "🔍",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️"
        }
        icon = icons.get(level.upper(), "•")
        
        # 格式化消息：[10:30:05] ✅ Query completed.
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {icon} {message}"
        
        self.terminal.push(formatted_msg)

    def _render_insight(self, message: str):
        """将结构化数据渲染到见解区并使其可见"""
        if not self.insight: return
        
        # 1. 更新内容
        self.insight.set_content(message)
        
        # 2. 确保它是显示的 (移除之前设定的 display: none)
        self.insight.style('display: block; opacity: 1;')
        
        # 3. 这里的逻辑可以加上：如果 Insight 有了新内容，自动展开父级 Expansion
        # self.components['insight_exp'].value = True

    async def switch_context(self, path: str):
        """实现基类定义的上下文切换"""
        if not path or path == '(None)': return
        
        # 1. 调用基类方法或直接操作组件
        self.components['chat_area'].clear()
        
        # 2. 执行 AiiDA 特有逻辑
        stats = await run.io_bound(get_database_summary)
        if stats['status'] == 'success':
            self.update_ui_component('welcome_title', f"Loaded {os.path.basename(path)}")
            msg = f"Database ready: {stats['node_count']} nodes"
            self.update_ui_component('welcome_sub', msg)
        
        # 3. 通知引擎同步
        await self.engine.run_once(intent=f"Inspect archive '{path}'. User task: System Refresh")
        
    async def select_archive(self, path):
        """环境重置联动：切换档案并更新欢迎屏"""
        if not path or path == '(None)': return
        self.components['archive_select'].value = path
        filename = os.path.basename(path)

        self.components['chat_area'].clear()
        self.components['welcome_screen'].set_visibility(True)
        self.components['suggestion_container'].set_visibility(True)

        stats = await run.io_bound(get_database_summary)
        if stats['status'] == 'success':
            self.components['welcome_title'].set_text(f"Loaded {filename}")
            self.components['welcome_title'].classes(replace='text-5xl font-light tracking-tight text-center text-primary opacity-100')
            
            sub_text = f"Database ready: {stats['node_count']} nodes • {stats['process_count']} processes"
            if stats.get('failed_count', 0) > 0:
                sub_text += f" • ⚠️ {stats['failed_count']} failed tasks detected"
            
            self.components['welcome_sub'].set_text(sub_text)
            ui.notify(f"Environment reset to {filename}", type='positive')
        
        # 🚩 档案感知记忆切换
        archive_name = os.path.basename(path).replace('.', '_')
        new_memory = JSONMemory(storage_dir=settings.MEMORY_DIR, namespace=archive_name)
        
        # 动态更换引擎的记忆模块
        self.engine._memory = new_memory
        
        
        await self.engine.run_once(intent=f"Inspect archive '{path}'. User task: System Refresh")

    async def pick_local_file(self):
        """处理本地文件选择"""
        def get_path():
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            p = filedialog.askopenfilename(filetypes=[("AiiDA Archives", "*.aiida *.zip")])
            root.destroy()
            return p

        selected_path = await run.io_bound(get_path)
        if selected_path:
            # 1. 获取当前历史
            history = self.global_mem.get_raw_data("recent_archives") or []

            # 2. 如果是新路径，则存入
            if selected_path not in history:
                history.append(selected_path)
                # 只保留最近 10 条
                self.global_mem.set_kv("recent_archives", history[-10:])
                
                # 3. 动态更新 UI (这里复用之前的 UI 添加代码)
                self._add_to_history_ui(selected_path)
                
            self.components['archive_select'].value = selected_path

    def render_suggestion_chips(self, suggestions):
        """在聊天区生成可点击的建议卡片"""
        if not suggestions: return
        
        with self.components['chat_area']:
            # 创建一个横向流式布局容器
            with ui.row().classes('flex-wrap gap-2 py-2 px-4 mb-4 animate-fade-in'):
                for text in suggestions:
                    # 🚩 核心：点击按钮直接触发 handle_send(text)
                    ui.button(
                        text, 
                        on_click=lambda t=text: self.handle_send(preset_text=t)
                    ).props('outline rounded dense no-caps').classes(
                        'text-[11px] px-3 py-1 border-primary/30 text-primary/80 '
                        'hover:bg-primary/10 hover:border-primary transition-all '
                        'bg-primary/5 capitalize italic'
                    )

    async def handle_send(self, preset_text=None):
        """处理消息发送（修复变量未定义错误）"""
        import os
        
        # 1. 获取输入
        text = preset_text if preset_text else self.components['input'].value
        if not text: return
        
        # 重置见解区
        if 'insight_view' in self.components:
            self.components['insight_view'].set_content('')
            self.components['insight_view'].style('display: none;')
        
        self.engine.log(f"Handling send: {text[:30]}...", level="DEBUG")

        # 2. UI 状态切换
        self.components['welcome_screen'].set_visibility(False)
        self.components['suggestion_container'].set_visibility(False)
        self.components['input'].value = ""

    async def handle_send(self, preset_text=None):
        """处理消息发送（深度定制 UI 对齐版）"""
        import os
        
        # 1. 获取并清理输入
        text = preset_text if preset_text else self.components['input'].value
        if not text: return
        
        # 重置：开始新对话时隐藏旧的见解区
        if 'insight_view' in self.components:
            self.components['insight_view'].set_content('')
            self.components['insight_view'].style('display: none;')
        
        # 2. UI 状态切换：隐藏欢迎词和固定建议
        self.components['welcome_screen'].set_visibility(False)
        self.components['suggestion_container'].set_visibility(False)
        self.components['input'].value = ""

        # 3. 【渲染用户消息】 - 强制靠右对齐
        with self.components['chat_area']:
            with ui.row().classes('w-full justify-end mb-6'):
                with ui.column().classes('items-end max-w-[80%]'):
                    ui.label('YOU').classes('text-[10px] font-black opacity-30 pr-2 tracking-tighter')
                    with ui.card().classes('bg-primary/10 p-4 rounded-2xl shadow-none border-none').style('border-bottom-right-radius: 2px;'):
                        ui.markdown(text).classes('text-slate-200 leading-relaxed')

            # 4. 【思考中状态】 - 靠左对齐
            thinking = ui.row().classes('items-center gap-3 pl-2 py-4 animate-pulse')
            with thinking:
                ui.avatar('auto_awesome', color='primary', text_color='white').props('size=sm')
                ui.label('SABR is thinking...').classes('text-xs text-slate-500 italic')

        # 初始滚动
        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
        
        try:
            # 4. 构造上下文意图
            arch_full_path = self.components['archive_select'].value
            intent = text
            # 🚩 修复点：先给 arch_name 默认值
            display_context = "Global"
            
            # 统一判断：只有路径存在且不为 (None) 时才处理
            if arch_full_path and arch_full_path != '(None)':
                arch_name = os.path.basename(arch_full_path)
                display_context = arch_name # 更新显示的上下文名称
                intent = f"Context: Inspect archive '{arch_full_path}'. Task on {arch_name}: {text}"
            
            # 5. 执行 Engine 循环
            # 🚩 使用统一的 display_context，不再报错
            self.engine.log(f"Consulting Brain with context: {display_context}", level="INFO")
            
            response = await self.engine.run_once(intent=intent)
            if not response: # 防御：如果 engine 返回了 None
                self.engine.log("Engine returned no data.", level="ERROR")
                return

            # 7. 【智能路由：渲染 AI 回复】
            # 如果内容是表格或长报告，依然去 insight_view；如果是对话，则出聊天气泡
            final_content = response.get("content", "")
            if response.get("action_name") != "say":
                 final_content = str(response.get("result", ""))

            # 🚩 核心逻辑：判断是发到气泡还是发到见解区
            if "|" in final_content and "---" in final_content:
                # 是表格：发到侧边见解区（之前调好的黑色大框）
                self.engine.log(final_content, level="SUCCESS") 
            else:
                # 是对话：在聊天区生成 AI 气泡
                with self.components['chat_area']:
                    with ui.row().classes('w-full justify-start mb-6'):
                        with ui.row().classes('items-start gap-3 no-wrap'):
                            ui.avatar('auto_awesome', color='primary', text_color='white').props('size=sm shadow-lg')
                            with ui.column().classes('max-w-[85%] items-start'):
                                ui.label('SABR-AIIDA').classes('text-[10px] font-black text-primary opacity-60 pl-1 tracking-tighter')
                                with ui.card().classes('bg-white/5 border border-white/10 p-4 rounded-2xl shadow-none').style('border-top-left-radius: 2px;'):
                                    ui.markdown(final_content).classes('text-slate-300 leading-relaxed')

            self.engine.log(final_content, level="SUCCESS")
            
            # 8. 渲染建议卡片
            suggestions = response.get("suggestions", [])
            if suggestions:
                # 🚩 确保 render_suggestion_chips 内部也是 max-w-[850px]
                self.render_suggestion_chips(suggestions)

            self.engine.log("Task completed.", level="SUCCESS")
            
        except Exception as e:
            # 打印完整的错误追踪到控制台，方便排查
            import traceback
            traceback.print_exc()
            self.engine.log(f"Critical error: {str(e)}", level="ERROR")
        
        finally:
            thinking.delete()
            ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

    def render_suggestion_chips(self, suggestions):
        with self.components['chat_area']:
            # 这里的 pl-12 是为了避开 AI 的头像宽度，让卡片对齐文字
            with ui.row().classes('flex-wrap gap-2 py-2 pl-12 mb-8 animate-fade-in'):
                for text in suggestions:
                    ui.button(
                        text, 
                        on_click=lambda t=text: self.handle_send(preset_text=t)
                    ).props('outline rounded dense no-caps shadow-none').classes(
                        'text-[11px] px-3 py-1 border-primary/20 text-primary/70 '
                        'hover:bg-primary/10 hover:border-primary transition-all '
                        'bg-white/5 italic'
                    )
    async def handle_model_change(self, e):
        """处理模型切换逻辑"""
        new_model = e.value
        
        # 1. 更新 Brain 实例的模型名称
        # 假设 GeminiBrain 暴露了 model_name 属性
        if hasattr(self.engine._brain, 'model_name'):
            self.engine._brain.model_name = new_model
            
        # 2. 记录到 Thought Log（黑色区域）
        self.engine.log(f"Brain configuration updated: model set to {new_model}", level="INFO")
        
        # 3. UI 反馈
        ui.notify(f"AI Model switched to {new_model}", 
                  color='primary', 
                  icon='psychology',
                  position='top-right')
        
        # 4. (可选) 如果你想让 AI 立即针对新模型打个招呼
        # await self.handle_send(preset_text="Hello! Are you ready with your new configuration?")
        
    async def handle_node_inspection(self, msg):
        """处理 ID 锚点点击"""
        from aiida.orm import load_node
        import json
        node_pk = msg.args.get('id')
        if not node_pk: return

        self.components['thought_log'].push(f"🔍 Fetching Node: {node_pk}...")
        try:
            node = await run.io_bound(load_node, int(node_pk))
            details = f"📄 *Node Detail:* {node_pk}\n---\n..." # 此处省略拼接逻辑
            self.components['debug_log'].set_content(details)
            self.components['debug_log'].classes(remove='insight-highlight')
            ui.timer(0.1, lambda: self.components['debug_log'].classes('insight-highlight'), once=True)
        except Exception as e:
            self.components['thought_log'].push(f"❌ Error: {str(e)}")

