# engines/aiida/ui/fastui.py
from fastui import AnyComponent
from fastui import components as c
from fastui import events as e
from fastui import forms as f
from sab_core.schema.response import SABRResponse
from sab_core.schema.request import AgentRequest
from fastui import FastUI

def get_process_panel(processes: list) -> list:
    """渲染最近的任务列表"""
    if not processes:
        return [c.Div(class_name="text-muted small px-2 py-3", components=[c.Text(text="No recent processes.")])]

    items = []
    for p in processes:
        # 根据 AiiDA 的 process_state 分配颜色
        state = p.get('state', '').lower()
        if state == 'finished':
            dot_style = "text-success"
        elif state in ['failed', 'excepted']:
            dot_style = "text-danger"
        elif state in ['running', 'waiting', 'created']:
            dot_style = "text-primary"
        else:
            dot_style = "text-secondary"

        items.append(
            c.Div(
                class_name="py-2 px-1 d-flex align-items-center gap-2 border-bottom border-light",
                components=[
                    # 🚩 状态圆点
                    c.Div(class_name=f"small {dot_style}", components=[c.Text(text="●")]),
                    # 🚩 任务信息
                    c.Div(components=[
                        c.Div(
                            class_name='text-dark small fw-bold text-truncate max-w-40', 
                            components=[c.Text(text=p.get('label'))]
                        ),
                        c.Div(
                            class_name="text-muted extra-small", 
                            components=[c.Text(text=f"PK: {p.get('pk')}")]
                        )
                    ])
                ]
            )
        )
    return items

def get_aiida_sidebar(profiles_display: list = None, processes: list = None) -> list[AnyComponent]:
    """
    重构侧边栏：
    途径 1: 系统 Profiles (Environment)
    途径 2: 本地 Archives (File Browser)
    """

    sidebar_content = []
    sidebar_content.append(
        c.Div(class_name="mb-5 mt-4 px-2", components=[
            # c.Div(class_name="text-dark fw-bold h5 mb-1", components=[c.Text(text="SABR v2.1")]),
            c.Div(class_name="text-muted small", components=[c.Text(text="AiiDA Expert")])
        ])
    )

    # --- Header: Profile + Icon Button ---
    sidebar_content.append(
        c.Div(
            class_name="d-flex justify-content-between align-items-center mb-4 mt-4 px-2",
            components=[
                c.Div(
                    class_name="text-dark fw-bold opacity-50 small",
                    components=[c.Text(text="PROFILE")]
                ),
                # 🚩 只有图标的导入按钮
                c.Link(
                    components=[c.Text(text="📂")],
                    on_click=e.GoToEvent(url='/aiida/archives/browse-local'),
                    class_name="btn btn-sm p-0 border-0 shadow-none text-dark",
                )
            ]
        )
    )
    # --- 渲染 Profile 列表 (包含系统和导入的) ---
    for profile_name, display_name, is_active in profiles_display:
        # 指示灯颜色：绿色(激活) vs 浅灰色(未激活)
        dot_color = "bg-success" if is_active else "bg-secondary opacity-25"
        

        sidebar_content.append(
            c.Link(
                components=[
                    c.Div(
                        # 激活的项目背景加深
                        class_name=(
                            "py-2 px-3 mb-2 rounded-3 d-flex align-items-center gap-2 border shadow-sm "
                            f"{'bg-light' if is_active  else 'bg-white'}"
                        ),
                        components=[
                            c.Div(
                                # 使用 p-1 (padding) 撑开 Div，rounded-circle 做成圆点
                                # d-inline-block 确保它是一个行内块级元素
                                class_name=f"rounded-circle {dot_color} p-1 d-inline-block",
                                components=[] # 🚩 必须提供空列表，否则 Pydantic 会报错
                            ),
                            # 🚩 名字
                            c.Div(
                                class_name=f"small {'fw-bold text-black' if is_active else 'text-dark'}",
                                components=[c.Text(text=display_name)]
                            )
                        ]
                    )
                ],
                on_click=e.GoToEvent(url=f'/aiida/profiles/switch/{profile_name}'),
                class_name="text-decoration-none"
            )
        )
    # 🚩 插入任务面板区域
    sidebar_content.append(
        c.Div(class_name="mt-5 px-2", components=[
            c.Div(
                class_name="text-dark fw-bold opacity-75 small uppercase mb-3", 
                components=[c.Text(text="Recent Tasks")]
            ),
            c.Sse(
                source='/api/aiida/processes/stream',
                components=[get_process_panel(processes)]
            )
        ])
    )
    return sidebar_content

def get_aiida_dashboard_layout(
    content: list[AnyComponent], 
    profiles_display: list = None, 
    processes: list = None) -> list[AnyComponent]:
    """
    Claude 布局：象牙灰底色 + 纯白圆角卡片。
    """
    return FastUI([
        c.PageTitle(text="SABR | Claude Style"),
        c.Navbar(
            title='SABR v2',
            title_event=e.GoToEvent(url='/aiida/'),
            class_name="sticky-top bg-white border-bottom border-dark border-opacity-10 py-1 shadow-none",
        ),
        c.Div(
            # 🚩 重点：bg-body-tertiary 是一种比 light 深、比 secondary 浅的中性暖灰
            class_name="container-fluid bg-body-tertiary min-vh-100 p-0", 
            components=[
                c.Div(
                    class_name="row g-0", 
                    components=[
                        # 侧边栏
                        c.Div(
                            class_name="col-md-3 vh-100 p-4 d-flex flex-column sticky-top border-end border-dark border-opacity-10",
                            components=get_aiida_sidebar(profiles_display=profiles_display, processes=processes)
                        ),
                        # 主内容区
                        c.Div(
                            class_name="col-md-9 p-4 p-md-5",
                            components=[
                                # 核心：纯白大卡片，超大圆角，使用细边框代替深色阴影
                                c.Div(
                                    class_name="bg-white p-4 p-lg-5 rounded-5 border border-dark border-opacity-10 mx-auto w-100",
                                    components=content
                                )
                            ]
                        ),
                    ]
                )
            ]
        )
    ])

def render_sabr_response(data: SABRResponse):
    suggestion_buttons = [
        c.Button(text=s, on_click=e.PageEvent(name=f's-{i}'), class_name="btn btn-outline-dark rounded-pill px-4 py-2 border-dark border-opacity-10") 
        for i, s in enumerate(data.suggestions)
    ]
    return [
        c.Heading(text="Research Analysis Outcome", level=2, class_name="text-dark fw-bold mb-4"),
        c.Div(class_name="lh-lg text-dark mb-5 fs-5", components=[c.Markdown(text=data.answer)]),
        c.Div(class_name="p-4 rounded-4 bg-body-tertiary border-0 mb-4", components=[
            c.Div(class_name="text-muted small fw-bold mb-2", components=[c.Text(text="REASONING STEPS")]),
            c.Div(components=[c.Paragraph(text=f"▹ {s}", class_name="small text-muted mb-1") for s in data.thought_process])
        ]),
        c.Div(class_name="d-flex flex-wrap gap-2 mt-5", components=suggestion_buttons)
    ]

def get_chat_interface():
    return [
        c.Div(class_name="py-4", components=[
            c.Heading(text="How can I help with your research?", level=2, class_name="fw-bold mb-4"),
            c.Div(class_name="p-4 bg-body-tertiary rounded-4", components=[
                c.ModelForm(model=AgentRequest, submit_url='/api/aiida/chat'),
            ])
        ])
    ]

def render_explorer(profiles: list, archives: list):
    """
    双面板浏览器：上方看 AiiDA Profiles，下方看本地 Archive 文件。
    """
    return [
        c.Div(class_name="mb-5", components=[
            c.Heading(text="AiiDA Profiles", level=3, class_name="fw-bold mb-3"),
            c.Paragraph(text="These are configured environments on your system.", class_name="text-muted small"),
            c.Table(
                data=profiles,
                columns=[
                    c.display.DisplayLookup(field='name', title='Profile Name'),
                    c.display.DisplayLookup(field='database_name', title='Database'),
                    c.display.DisplayLookup(field='repository', title='Repository Path'),
                    # 可以在这里加一个 'Load' 按钮
                ],
            ),
        ]),
        
        c.Div(class_name="mb-5 pt-4 border-top", components=[
            c.Heading(text="Local Archives", level=3, class_name="fw-bold mb-3"),
            c.Paragraph(text="Standalone .aiida files found in current directory.", class_name="text-muted small"),
            c.Table(
                data=archives,
                columns=[
                    c.display.DisplayLookup(field='name', title='File Name'),
                    c.display.DisplayLookup(field='size', title='Size'),
                    c.display.DisplayLink(
                        field='name',
                        title='Action',
                        link='/aiida/archive/{name}',
                        label='View Content'
                    ),
                ],
            ),
        ]),
        
        c.Div(class_name="p-4 bg-body-tertiary rounded-4 border border-dashed text-center", components=[
            c.Text(text="Scan new directory for archives? "),
            c.Button(text="Trigger Scan", on_click=e.GoToEvent(url='/aiida/explorer?refresh=true'), 
                     class_name="btn btn-sm btn-dark ms-2")
        ])
    ]