# engines/aiida/ui/fastui.py
from fastui import AnyComponent
from fastui import components as c
from fastui import events as e
from fastui import forms as f
from sab_core.schema.response import SABRResponse
from sab_core.schema.request import AgentRequest

def get_aiida_sidebar() -> list[AnyComponent]:
    """
    重构侧边栏：Gemini 风格的白色卡片组件化布局。
    """
    archives = ["initial_structure.aiida", "surface_relaxation.aiida"]
    processes = [
        {"id": "101", "label": "PwCalculation", "status": "Finished"},
        {"id": "102", "label": "DosCalculation", "status": "Running"}
    ]

    sidebar_content = []
    
    # --- 组件 1: Archive 卡片 ---
    sidebar_content.append(
        c.Div(
            class_name="bg-white p-3 rounded-4 shadow-sm border-0 mb-4", 
            components=[
                c.Div(class_name="text-primary fw-bold small mb-3", components=[c.Text(text="📦 ARCHIVES")]),
                c.LinkList(
                    links=[
                        c.Link(
                            components=[c.Text(text=a)],
                            on_click=e.GoToEvent(url=f'/ui/archive/{a}'),
                            class_name="py-1 text-secondary small"
                        ) for a in archives
                    ]
                )
            ]
        )
    )

    # --- 组件 2: 任务动态卡片 ---
    sidebar_content.append(
        c.Div(
            class_name="bg-white p-3 rounded-4 shadow-sm border-0 mb-4",
            components=[
                c.Div(class_name="text-primary fw-bold small mb-3", components=[c.Text(text="⚡ RECENT TASKS")]),
                c.Div(components=[
                    c.Div(
                        class_name="d-flex align-items-center justify-content-between mb-2 pb-2 border-bottom border-light",
                        components=[
                            c.Div(class_name="small text-dark", components=[c.Text(text=f"PK {p['id']}")]),
                            c.Div(
                                class_name=f"badge {'bg-success-subtle text-success' if p['status']=='Finished' else 'bg-warning-subtle text-warning'} border-0 px-2",
                                components=[c.Text(text=p['status'])]
                            )
                        ]
                    ) for p in processes
                ])
            ]
        )
    )

    # --- 组件 3: 系统监控卡片 ---
    sidebar_content.append(
        c.Div(
            class_name="bg-primary text-white p-3 rounded-4 shadow-sm mt-auto",
            components=[
                c.Div(class_name="fw-bold small", components=[c.Text(text="System Pulse")]),
                c.Div(class_name="opacity-75 small", components=[c.Text(text="AiiDA Core: Connected")])
            ]
        )
    )

    return sidebar_content

def get_aiida_dashboard_layout(content: list[AnyComponent]) -> list[AnyComponent]:
    """
    主布局：Gemini/Notion 风格。
    侧边栏与主区背景一致，通过卡片阴影区分功能。
    """
    return [
        c.PageTitle(text="SABR v2 | AiiDA Dashboard"),
        c.Navbar(
            title='SABR v2',
            title_event=e.GoToEvent(url='/ui/'),
            class_name="sticky-top shadow-none border-bottom bg-white py-2",
        ),
        c.Div(
            class_name="container-fluid bg-light", # 全局背景浅灰色
            components=[
                c.Div(
                    class_name="row g-0", 
                    components=[
                        # 侧边栏：浅灰色背景，不与主区分割，靠卡片自成一体
                        c.Div(
                            class_name="col-md-3 vh-100 p-4 d-flex flex-column sticky-top",
                            components=get_aiida_sidebar() 
                        ),
                        # 主内容区
                        c.Div(
                            class_name="col-md-9 p-4",
                            components=[
                                c.Div(
                                    class_name="bg-white p-5 rounded-4 shadow-sm min-vh-100 border border-light",
                                    components=content
                                )
                            ]
                        ),
                    ]
                )
            ]
        )
    ]

# 其余渲染函数 (render_sabr_response, get_chat_interface) 保持 Pydantic 规范...
def get_chat_interface():
    return [
        c.Heading(text="Research Intelligence", level=2, class_name="mb-4"),
        c.ModelForm(model=AgentRequest, submit_url='/api/ui/chat', class_name="p-0"),
    ]

def render_sabr_response(data: SABRResponse):
    return [
        c.Heading(text="Analysis Result", level=2, class_name="mb-4"),
        c.Div(class_name="p-4 border-start border-4 border-primary bg-light mb-4", components=[
            c.Markdown(text=data.answer),
        ]),
        c.Details(label="Thought Process", content=[c.Paragraph(text=s) for s in data.thought_process])
    ]