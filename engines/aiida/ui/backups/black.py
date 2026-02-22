# engines/aiida/ui/fastui.py
from fastui import AnyComponent
from fastui import components as c
from fastui import events as e
from fastui import forms as f
from sab_core.schema.response import SABRResponse
from sab_core.schema.request import AgentRequest

def get_aiida_sidebar() -> list[AnyComponent]:
    """
    构建侧边栏。修复了 c.Text 带有 class_name 的错误。
    """
    # 模拟数据
    archives = ["initial_structure.aiida", "surface_relaxation.aiida"]
    processes = [{"id": "101", "label": "PwCalculation", "status": "Finished"}]

    sidebar_content = []
    
    # 1. Archive Section
    sidebar_content.append(
        c.Div(class_name="mb-4", components=[
            c.Heading(text="ARCHIVE HISTORY", level=6, class_name="text-uppercase text-secondary small fw-bold mb-3 letter-spacing-1"),
            c.Div(class_name="d-grid gap-2", components=[
                c.Link(
                    components=[
                        c.Div(
                            class_name="p-2 rounded border border-secondary bg-secondary bg-opacity-10 text-light hover-bg-opacity-20 transition-all",
                            components=[c.Text(text=f"📦 {a}")]
                        )
                    ],
                    on_click=e.GoToEvent(url=f'/ui/archive/{a}'),
                ) for a in archives
            ])
        ])
    )    


    # 2. Recent Processes
# --- 组件 2: Recent Processes 动态列表 ---
    sidebar_content.append(
        c.Div(class_name="mb-4", components=[
            c.Heading(text="RECENT TASKS", level=6, class_name="text-uppercase text-secondary small fw-bold mb-3"),
            c.Div(class_name="list-group list-group-flush rounded overflow-hidden", components=[
                c.Div(
                    class_name="list-group-item bg-transparent border-secondary border-opacity-20 py-2 px-1 text-light small d-flex justify-content-between align-items-center",
                    components=[
                        c.Text(text=f"PK {p['id']}: {p['label']}"),
                        c.Div(
                            class_name=f"badge rounded-pill {'bg-success' if p['status']=='Finished' else 'bg-warning text-dark'}",
                            components=[c.Text(text=p['status'])]
                        )
                    ]
                ) for p in processes
            ])
        ])
    )
    # 3. Status
    sidebar_content.append(
        c.Div(
            class_name="mt-auto p-3 rounded bg-primary bg-opacity-10 border border-primary border-opacity-20",
            components=[
                c.Div(class_name="text-primary small fw-bold", components=[c.Text(text="● AiiDA Online")]),
                c.Div(class_name="text-secondary small", components=[c.Text(text="V2.1 Standard Profile")])
            ]
        )
    )

    return sidebar_content

def get_aiida_dashboard_layout(content: list[AnyComponent]) -> list[AnyComponent]:
    """
    主布局。增加了 pt-5 避开悬浮 Navbar。
    """
    return [
        c.PageTitle(text="SABR v2 | AiiDA Dashboard"),
        c.Navbar(
            title='SABR v2',
            title_event=e.GoToEvent(url='/ui/'),
            class_name="sticky-top shadow-sm bg-white",
        ),
        c.Div(
            class_name="container-fluid", 
            components=[
                c.Div(
                    class_name="row mt-2",
                    components=[
                        # 左侧边栏
                        c.Div(
                            class_name="col-md-3 vh-100 bg-dark p-4 d-flex flex-column sticky-top",
                            components=get_aiida_sidebar() 
                        ),
                        # 右侧主区
                        c.Div(
                            class_name="col-md-9 bg-light p-5 vh-100 overflow-auto",
                            components=[
                                c.Div(
                                    class_name="bg-white p-5 rounded-4 shadow-sm min-vh-100",
                                    components=content
                                )
                            ]
                        ),
                    ]
                )
            ]
        )
    ]

# 保持其他函数不变...
def get_chat_interface():
    return [
        c.Heading(text="Research Intelligence", level=2),
        c.ModelForm(model=AgentRequest, submit_url='/api/ui/chat'),
    ]

def render_sabr_response(data: SABRResponse):
    return [
        c.Heading(text="Analysis Result", level=2),
        c.Div(class_name="p-4 border-start border-4 border-primary bg-white shadow-sm mb-4", components=[
            c.Markdown(text=data.answer),
        ]),
        c.Details(label="Thought Process", content=[c.Paragraph(text=s) for s in data.thought_process])
    ]