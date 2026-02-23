# engines/aiida/ui/fastui.py
from fastui import AnyComponent
from fastui import components as c
from fastui import events as e
from sab_core.schema.response import SABRResponse
from sab_core.schema.request import AgentRequest

def get_aiida_sidebar() -> list[AnyComponent]:
    """
    Refactor sidebar with Gemini-style white-card composition.
    """
    archives = ["initial_structure.aiida", "surface_relaxation.aiida"]
    processes = [
        {"id": "101", "label": "PwCalculation", "status": "Finished"},
        {"id": "102", "label": "DosCalculation", "status": "Running"}
    ]

    sidebar_content = []
    
    # --- Component 1: archive card ---
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

    # --- Component 2: recent-task card ---
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

    # --- Component 3: system-status card ---
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
    Main layout in Gemini/Notion style.
    Sidebar and main area share the background; cards provide visual separation.
    """
    return [
        c.PageTitle(text="SABR v2 | AiiDA Dashboard"),
        c.Navbar(
            title='SABR v2',
            title_event=e.GoToEvent(url='/ui/'),
            class_name="sticky-top shadow-none border-bottom bg-white py-2",
        ),
        c.Div(
            class_name="container-fluid bg-light",  # Global light-gray background.
            components=[
                c.Div(
                    class_name="row g-0", 
                    components=[
                        # Sidebar: same light background, cards define boundaries.
                        c.Div(
                            class_name="col-md-3 vh-100 p-4 d-flex flex-column sticky-top",
                            components=get_aiida_sidebar() 
                        ),
                        # Main content area.
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

# Keep remaining render helpers consistent with FastUI/Pydantic expectations.
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
