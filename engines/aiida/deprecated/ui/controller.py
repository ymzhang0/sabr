import os
import httpx
import tkinter as tk
from tkinter import filedialog
from nicegui import ui, run
from src.sab_core.protocols.controller import BaseController

class RemoteAiiDAController(BaseController):
    """
    AiiDA 远程逻辑控制器
    职责：通过 API 与后端通信，同时维持原汁原味的 NiceGUI 复杂布局。
    """
    def __init__(self, api_url: str, components: dict, memory):
        # 在远程模式下，engine 属性存储的是 API URL
        super().__init__(engine=api_url, components=components)
        self.api_url = api_url
        self.global_mem = memory
        self.client = httpx.AsyncClient(base_url=api_url, timeout=60.0)
        
        # 恢复你原来的状态绑定
        self._load_archive_history()
        self.ticker_timer = ui.timer(10.0, self.update_process_status)
        self.terminal = components.get('thought_log')
        self.insight = components.get('insight_view')

    # ============================================================
    # 🎨 原封不动的 UI 渲染逻辑 (布局保卫战)
    # ============================================================

    def _prepare_ui(self):
        if 'insight_view' in self.components:
            self.components['insight_view'].set_content('')
            self.components['insight_view'].style('display: none;')
        self.components['welcome_screen'].set_visibility(False)
        self.components['suggestion_container'].set_visibility(False)
        self.components['input'].value = ""

    def _create_chat_bubble(self, text: str, role: str = 'user'):
        """完美保留你之前的气泡样式"""
        with self.components['chat_area']:
            if role == 'user':
                with ui.row().classes('w-full justify-end mb-6'):
                    with ui.column().classes('items-end max-w-[80%]'):
                        ui.label('YOU').classes('text-[10px] font-black opacity-30 pr-2 tracking-tighter')
                        with ui.card().classes('bg-primary/10 p-4 rounded-2xl shadow-none border-none').style('border-bottom-right-radius: 2px;'):
                            ui.markdown(text).classes('text-slate-200 leading-relaxed')
            else:
                with ui.row().classes('w-full justify-start mb-6'):
                    with ui.row().classes('items-start gap-3 no-wrap'):
                        ui.avatar('auto_awesome', color='primary', text_color='white').props('size=sm shadow-lg')
                        with ui.column().classes('max-w-[85%] items-start'):
                            ui.label('SABR-AIIDA').classes('text-[10px] font-black text-primary opacity-60 pl-1 tracking-tighter')
                            with ui.card().classes('bg-white/5 border border-white/10 p-4 rounded-2xl shadow-none').style('border-top-left-radius: 2px;'):
                                ui.markdown(text).classes('text-slate-300 leading-relaxed')
        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

    # ============================================================
    # 📡 核心业务重构：API 驱动
    # ============================================================

    async def handle_send(self, preset_text=None):
        text = preset_text if preset_text else self.components['input'].value
        if not text: return

        self._prepare_ui()
        self._create_chat_bubble(text, role='user')

        # 思考区渲染 (保留原来的 Expansion 逻辑)
        with self.components['chat_area']:
            with ui.expansion('', icon='psychology').classes('w-full mb-2 text-slate-400') as thought_exp:
                with thought_exp.add_slot('header'):
                    thought_topic = ui.label('SABR is connecting to API...').classes('text-xs italic ml-2')
                detail_log = ui.log().classes('w-full h-32 text-[10px] bg-slate-900/50 p-2')
            
            # AI 回复容器 (用于流式更新)
            with ui.row().classes('w-full justify-start mb-6') as ai_response_row:
                 # 这里我们先不渲染内容，等 API 返回
                 pass

        try:
            # 🚩 向远程后端发起请求
            # 注意：此处为简化，使用普通 POST，若需流式则需后端支持 StreamingResponse
            response = await self.client.post("/v1/chat", json={
                "intent": text,
                "context_archive": self.components['archive_select'].value
            })
            
            if response.status_code == 200:
                data = response.json()
                thought_topic.set_text("Thinking completed.")
                thought_exp.value = False # 自动折叠
                
                # 路由结果：决定去气泡还是去 Insight View
                content = data.get('content', '')
                if "|" in content and "---" in content:
                    self._render_insight(content)
                else:
                    self._create_chat_bubble(content, role='ai')
                
                # 渲染建议按钮
                if data.get('suggestions'):
                    self.render_suggestion_chips(data['suggestions'])
            else:
                detail_log.push(f"❌ API Error: {response.status_code}")
        except Exception as e:
            detail_log.push(f"❌ Connection Error: {str(e)}")
        finally:
            ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

    async def update_process_status(self):
        """远程获取进程状态 Ticker"""
        archive = self.components['archive_select'].value
        if not archive or archive == "(None)": return

        try:
            r = await self.client.get("/v1/aiida/processes")
            if r.status_code == 200:
                processes = r.json()
                # 这里的渲染逻辑可以根据你的 Reporter 结构进行调整
                # 简单起见，如果 components 里有状态条，直接更新
                self._render_terminal(f"Backend Ticker: {len(processes)} active processes found.", "DEBUG")
        except:
            pass

    async def switch_context(self, path: str):
        """实现基类的上下文切换"""
        if not path or path == '(None)': return
        filename = os.path.basename(path)
        
        self.components['chat_area'].clear()
        self.components['welcome_screen'].set_visibility(True)
        
        try:
            # 🚩 向 API 获取数据库概要
            r = await self.client.get("/v1/aiida/summary")
            if r.status_code == 200:
                stats = r.json()
                self.components['welcome_title'].set_text(f"Loaded {filename}")
                self.components['welcome_sub'].set_text(
                    f"Database ready: {stats['node_count']} nodes • {stats['process_count']} processes"
                )
                ui.notify(f"Remote Environment set to {filename}", type='positive')
        except Exception as e:
            ui.notify(f"Failed to switch context: {e}", type='negative')

    async def handle_node_inspection(self, msg):
        """处理 ID 锚点点击 (远程版)"""
        node_pk = msg.args.get('id')
        if not node_pk: return
        
        self._render_terminal(f"Remote fetching Node: {node_pk}...", "INFO")
        try:
            r = await self.client.get(f"/v1/aiida/nodes/{node_pk}")
            if r.status_code == 200:
                details = r.json()
                # 渲染到 Debug/Insight 面板
                self.components['insight_view'].set_content(f"## Node {node_pk}\n```json\n{details}\n```")
                self.components['insight_view'].style('display: block;')
        except Exception as e:
            self._render_terminal(f"Error: {e}", "ERROR")

    # ============================================================
    # 🗃️ 辅助逻辑 (保持原样)
    # ============================================================
    
    def _render_terminal(self, message: str, level: str):
        if not self.terminal: return
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.terminal.push(f"[{timestamp}] {level}: {message}")

    def _render_insight(self, message: str):
        if not self.insight: return
        self.insight.set_content(message)
        self.insight.style('display: block; opacity: 1;')

    def _load_archive_history(self):
        history = self.global_mem.get_raw_data("recent_archives") or []
        self.components['archive_select'].options = history
        with self.components['archive_history']:
            for path in history:
                self._add_to_history_ui(path)

    def _add_to_history_ui(self, path: str):
        filename = os.path.basename(path)
        with self.components['archive_history']:
            ui.item(on_click=lambda: self.switch_context(path)).classes('px-8 py-2 rounded-xl hover:bg-white/5 cursor-pointer') \
                .child(ui.label(filename).classes('text-[11px] text-slate-400'))

    async def pick_local_file(self):
        """保持 tkinter 逻辑，因为它是在客户端运行的"""
        def get_path():
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            p = filedialog.askopenfilename(filetypes=[("AiiDA Archives", "*.aiida *.zip")])
            root.destroy()
            return p
        selected_path = await run.io_bound(get_path)
        if selected_path:
            self.switch_context(selected_path)

    async def close(self):
        await self.client.aclose()