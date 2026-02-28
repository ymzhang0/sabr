import os
import httpx
import tkinter as tk
from tkinter import filedialog
from nicegui import ui, run
from src.sab_core.protocols.controller import BaseController

class RemoteAiiDAController(BaseController):
    """
    Complete AiiDA Remote Controller for SABR v2.
    Fully restores bubble styling, terminal updates, and cyclic interaction.
    """
    def __init__(self, api_url: str, components: dict, memory):
        super().__init__(engine=api_url, components=components)
        self.api_url = api_url
        self.global_mem = memory
        self.client = httpx.AsyncClient(base_url=api_url, timeout=120.0)
        
        # State Initialization
        self._load_archive_history()
        self.ticker_timer = ui.timer(10.0, self.update_process_status)
        self.terminal = components.get('thought_log')
        self.insight = components.get('insight_view')

    # ============================================================
    # 🎨 Original UI Rendering Logic
    # ============================================================

    def _prepare_ui(self):
        if self.insight:
            self.insight.set_content('')
            self.insight.style('display: none;')
        self.components['welcome_screen'].set_visibility(False)
        self.components['suggestion_container'].set_visibility(False)
        self.components['input'].value = ""

    def _create_chat_bubble(self, text: str, role: str = 'user'):
        """Restores the exact bubble styling from your original code."""
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
    # 📡 SABR v2 Core Logic
    # ============================================================

    async def handle_send(self, preset_text=None):
        text = preset_text if preset_text else self.components['input'].value
        if not text: return

        self._prepare_ui()
        self._create_chat_bubble(text, role='user')

        # Thinking Animation (Expansion log)
        with self.components['chat_area']:
            with ui.expansion('', icon='psychology').classes('w-full mb-2 text-slate-400') as thought_exp:
                with thought_exp.add_slot('header'):
                    thought_topic = ui.label('Agent is reasoning in cyclic loops...').classes('text-xs italic ml-2')
                step_log = ui.log().classes('w-full h-32 text-[10px] bg-slate-900/50 p-2')

        try:
            # Call SABR v2 API
            response = await self.client.post("/v1/chat", json={
                "intent": text,
                "context_archive": self.components['archive_select'].value
            })
            
            if response.status_code == 200:
                data = response.json()
                
                # 1. Update terminal steps from the backend
                for step in data.get('thought_process', []):
                    step_log.push(f"⚙️ {step}")
                    self._render_terminal(step, "INFO")
                
                thought_topic.set_text("Cycles completed.")
                thought_exp.value = False # Auto-collapse

                # 2. Render Answer
                self._create_chat_bubble(data.get('answer', ''), role='ai')
                
                # 3. Handle Data Payload (Insight View)
                if data.get('data_payload'):
                    self._render_insight(data['data_payload'])
                
                # 4. Render Smart Chips (Suggestions)
                if data.get('suggestions'):
                    self._render_suggestions(data['suggestions'])
            else:
                self._render_terminal(f"API Error: {response.status_code}", "ERROR")
        except Exception as e:
            self._render_terminal(f"Connection Error: {str(e)}", "ERROR")
        finally:
            ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')

    async def update_process_status(self):
        """Ticker for monitoring AiiDA processes."""
        archive = self.components['archive_select'].value
        if not archive or archive == "(None)": return
        try:
            r = await self.client.get("/v1/aiida/processes")
            if r.status_code == 200:
                processes = r.json()
                # Here we could render them into components['process_ticker']
                # For now, just a terminal log for safety
                if processes:
                    self._render_terminal(f"Ticker: {len(processes)} active processes.", "DEBUG")
        except: pass

    async def switch_context(self, path: str):
        """Switch AiiDA environment context."""
        if not path or path == '(None)': return
        filename = os.path.basename(path)
        self.components['chat_area'].clear()
        self.components['welcome_screen'].set_visibility(True)
        try:
            r = await self.client.get("/v1/aiida/summary")
            if r.status_code == 200:
                stats = r.json()
                self.components['welcome_title'].set_text(f"Loaded {filename}")
                self.components['welcome_sub'].set_text(f"Database ready: {stats['node_count']} nodes • {stats['process_count']} processes")
                ui.notify(f"Switched to {filename}", type='positive')
        except: ui.notify("Failed to fetch DB summary", type='negative')

    async def handle_node_inspection(self, msg):
        """Handle Node ID clicks via JS emit."""
        pk = msg.args.get('id')
        if not pk: return
        self._render_terminal(f"Inspecting Node {pk}...", "INFO")
        try:
            r = await self.client.get(f"/v1/aiida/nodes/{pk}")
            if r.status_code == 200:
                self._render_insight(r.json())
        except: pass

    # ============================================================
    # 🗃️ Helper Rendering Methods
    # ============================================================

    def _render_terminal(self, message: str, level: str):
        if not self.terminal: return
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        icons = {"INFO": "🔹", "DEBUG": "🔍", "SUCCESS": "✅", "ERROR": "❌"}
        self.terminal.push(f"[{ts}] {icons.get(level, '•')} {message}")

    def _render_insight(self, data: any):
        if not self.insight: return
        import json
        formatted = json.dumps(data, indent=2) if isinstance(data, dict) else str(data)
        self.insight.set_content(f"### Current Insight\n```json\n{formatted}\n```")
        self.insight.style('display: block; opacity: 1;')

    def _render_suggestions(self, suggestions: list):
        with self.components['chat_area']:
            with ui.row().classes('gap-2 py-2 ml-12 mb-8'):
                for s in suggestions:
                    ui.button(s, on_click=lambda text=s: self.handle_send(text)) \
                        .props('outline rounded dense no-caps shadow-none') \
                        .classes('text-[11px] px-3 border-primary/20 text-primary/70 hover:bg-primary/10 transition-all italic')

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
        def get_path():
            root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
            p = filedialog.askopenfilename(filetypes=[("AiiDA Archives", "*.aiida *.zip")])
            root.destroy()
            return p
        selected_path = await run.io_bound(get_path)
        if selected_path: self.switch_context(selected_path)

    async def close(self):
        await self.client.aclose()