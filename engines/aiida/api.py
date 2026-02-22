# engines/aiida/api.py
from fastapi import APIRouter, Request
from fastui import FastUI, AnyComponent
from fastui import components as c
from fastui import events as e
from .ui.fastui import get_aiida_dashboard_layout, get_chat_interface, render_sabr_response, render_explorer
from sab_core.schema.request import AgentRequest
from .ui import fastui as ui
from loguru import logger

from fastapi.concurrency import run_in_threadpool
import tkinter as tk
from tkinter import filedialog
from .hub import hub
from pathlib import Path
from .tools import get_recent_processes
from sse_starlette.sse import EventSourceResponse
import asyncio

def ask_for_folder_path():
    """
    在服务器端（你的本地电脑）弹出一个原生的文件夹选择对话框。
    """
    logger.info("🖥️ Opening native folder dialog on host OS...")
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    root.attributes('-topmost', True)  # 确保对话框在最前面
    
    # 弹出选择文件夹窗口
    file_selected = filedialog.askopenfilename(
        title="Select AiiDA Archive",
        filetypes=[("AiiDA Archive", "*.aiida"), ("Zip Archive", "*.zip"), ("All Files", "*.*")]
    )
    
    root.destroy() # 关闭 tkinter
    
    if file_selected:
        logger.success(f"📂 User selected: {file_selected}")
        return file_selected
    else:
        logger.warning("🚫 User cancelled folder selection.")
        return None


router = APIRouter()

@router.get("/processes/stream")
async def stream_processes(request: Request):
    """
    这是一个 SSE 接口，每隔 3 秒向前端推送一次最新的任务状态
    """
    async def event_generator():
        while True:
            # 如果客户端断开了连接，停止循环
            if await request.is_disconnected():
                break

            # 🚩 1. 获取最新数据
            try:
                # 确保这里调用的是带缓存或足够快的查询逻辑
                processes = tools.get_recent_processes()
                
                # 🚩 2. 构建要推送的 UI 组件
                # 我们只推送任务面板那一部分的组件
                body = ui.get_process_panel(processes)
                
                # 🚩 3. 包装成 FastUI 格式推送
                # 将组件序列化为 JSON
                yield {
                    "data": FastUI(root=[body]).model_dump_json()
                }
            except Exception as e:
                logger.error(f"Streaming error: {e}")

            # 🚩 4. 频率控制（比如 3 秒刷新一次）
            await asyncio.sleep(3)

    return EventSourceResponse(event_generator())
      
# 1. 仪表盘主页 (http://localhost:8000/ui/)
@router.get("/", response_model=FastUI, response_model_exclude_none=True)
async def aiida_ui_root() -> FastUI:

    hub.start()
    # 2. 🚩 调用你提供的工具函数获取任务
    try:
        # 数据库查询逻辑完全封装在 tools.py 内部
        recent_procs = get_recent_processes(limit=5)
    except Exception as e:
        logger.error(f"Failed to fetch processes: {e}")
        recent_procs = []

    # 3. 准备主区域内容：默认显示聊天输入框
    chat_content = ui.get_chat_interface()

    # 4. 渲染整体布局
    return ui.get_aiida_dashboard_layout(
        content=chat_content,
        profiles_display=hub.get_display_list(),
        processes=recent_procs # 传入数据
    )
 


@router.get("/archives/browse-local", response_model=FastUI)
async def trigger_native_browse():
    
    # 1. 弹出原生窗口
    selected_file = await run_in_threadpool(ask_for_folder_path)
    
    if selected_file:
        # 🚩 关键：动态存入内存/文件
        hub.import_archive(Path(selected_file))
        logger.info(f"Dynamically expanded profiles with: {selected_file}")
    
    # 2. 刷新页面。刷新时 aiida_ui_root 会被重新调用
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/'))])

@router.get("/profiles/switch/{name}", response_model=FastUI)
async def handle_switch(name: str):
    # 🚩 切换逻辑：更新环境变量或全局状态
    hub.switch_profile(name)
    return FastUI(root=[c.FireEvent(event=e.GoToEvent(url='/aiida/'))])

# 2. 聊天输入页 (http://localhost:8000/aiida/chat)
# 当用户点击 "Start New Analysis" 或直接访问该路径时触发
@router.get("/aiida/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_input_page() -> FastUI:
    # 返回我们在 fastui.py 中定义的 ModelForm
    return get_aiida_dashboard_layout(get_chat_interface())

# 3. Agent 执行与结果返回
# 当用户在 ModelForm 点击提交时，FastUI 会自动 POST 到这里
@router.post("/aiida/chat", response_model=FastUI, response_model_exclude_none=True)
async def aiida_chat_handler(request: Request, form: AgentRequest):
    """
    核心：接收表单数据，运行 PydanticAI，返回结果界面。
    """
    state = request.app.state
    agent = getattr(state, "agent", None)
    DepsClass = getattr(state, "deps_class", None)
    
    # 获取表单中的用户意图
    user_intent = form.intent 
    context_archive = form.context_archive

    try:
        # 实例化依赖并运行 Agent
        current_deps = DepsClass(
            archive_path=context_archive,
            memory=state.memory
        )
        
        # 运行 PydanticAI 循环
        result = await agent.run(user_intent, deps=current_deps)
        
        # 填充思考轨迹
        if hasattr(current_deps, "step_history"):
            result.data.thought_process = current_deps.step_history
            
        # 🚩 直接返回渲染好的结果布局
        return get_aiida_dashboard_layout(render_sabr_response(result.data))

    except Exception as e:
        return get_aiida_dashboard_layout([
            c.Heading(text="Analysis Error", level=2),
            c.Markdown(text=f"Something went wrong: `{str(e)}`"),
            c.Button(text="Back to Chat", on_click=c.GoToEvent(url='/aiida/chat'))
        ])