import os
import tkinter as tk
from tkinter import filedialog
from nicegui import ui, run
from engines.aiida.tools.management.profile import get_database_summary
from sab_core.protocols.controller import BaseController
from sab_core.memory.json_memory import JSONMemory

class AiiDAController(BaseController):
    """
    AiiDA 引擎专用控制器
    实现具体的 AiiDA 数据库操作与 NiceGUI 组件的绑定
    """
    def __init__(self, engine, components):
        super().__init__(engine, components)
        self.global_mem = JSONMemory(storage_dir="engines/aiida/data/memories", namespace="global_config")
        # 🚩 启动时自动恢复历史列表
        self._load_archive_history()
    
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
                    .classes('rounded-xl hover:bg-blue-50 px-3 cursor-pointer'):
                    with ui.item_section():
                        ui.label(filename).classes('text-xs')

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
        new_memory = JSONMemory(storage_dir="engines/aiida/data/memories", namespace=archive_name)
        
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

    async def handle_send(self, preset_text=None):
        """处理消息发送"""
        self.engine.log(f"Handling send: {preset_text or 'input text'}", level="DEBUG")
        text = preset_text if preset_text else self.components['input'].value
        if not text: return
        
        self.components['welcome_screen'].set_visibility(False)
        self.components['suggestion_container'].set_visibility(False)
        self.components['input'].value = ""

        with self.components['chat_area']:
            ui.chat_message(text, name='You', sent=True).classes('self-end w-full')
            thinking = ui.row().classes('items-center gap-2 pl-4')
            with thinking:
                ui.spinner(size='xs'); ui.label('Processing...').classes('text-xs text-grey-5')

        ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
        
        try:
            arch_full_path = self.components['archive_select'].value
            intent = text
            if arch_full_path and arch_full_path != '(None)':
                arch_name = os.path.basename(arch_full_path)
                intent = f"Context: Inspect archive '{arch_full_path}'. Task on {arch_name}: {text}"
            
            self.engine.log("Querying Gemini Brain...", level="INFO")
            await self.engine.run_once(intent=intent)
            self.engine.log("Engine cycle completed.", level="INFO")
        except Exception as e:
            self.engine.log(f"Fatal in handle_send: {str(e)}", level="ERROR")
        finally:
            thinking.delete()

    async def handle_node_inspection(self, msg):
        """处理 ID 锚点点击"""
        from aiida.orm import load_node
        import json
        node_pk = msg.args.get('id')
        if not node_pk: return

        self.components['thought_log'].push(f"🔍 Fetching Node: {node_pk}...")
        try:
            node = await run.io_bound(load_node, int(node_pk))
            details = f"### 📄 Node Detail: {node_pk}\n---\n..." # 此处省略拼接逻辑
            self.components['debug_log'].set_content(details)
            self.components['debug_log'].classes(remove='insight-highlight')
            ui.timer(0.1, lambda: self.components['debug_log'].classes('insight-highlight'), once=True)
        except Exception as e:
            self.components['thought_log'].push(f"❌ Error: {str(e)}")

