# engines/aiida/ui/fastui.py
from fastui import AnyComponent
from fastui import components as c
from fastui import events as e
from sab_core.schema.response import SABRResponse
from sab_core.schema.request import AgentRequest

def get_aiida_sidebar() -> list[AnyComponent]:
    """
    Refactor sidebar to an industrial-console style.
    Remove all non-standard inline style attributes.
    """
    archives = ["initial_structure.aiida", "surface_relaxation.aiida"]
    processes = [
        {"id": "101", "label": "PwCalculation", "status": "Finished"},
        {"id": "102", "label": "DosCalculation", "status": "Running"}
    ]

    sidebar_content = []
    
    # --- Section: ARCHIVES ---
    sidebar_content.append(
        c.Div(class_name="mb-4", components=[
            c.Div(class_name="text-info small fw-bold mb-2", components=[c.Text(text="📡 DATA ARCHIVES")]),
            c.Div(class_name="d-grid gap-2", components=[
                c.Link(
                    components=[
                        c.Div(
                            class_name="p-2 rounded border border-info border-opacity-25 bg-info bg-opacity-10 text-white small",
                            components=[c.Text(text=f"📂 {a}")]
                        )
                    ],
                    on_click=e.GoToEvent(url=f'/ui/archive/{a}'),
                ) for a in archives
            ])
        ])
    )

    # --- Section: LIVE MONITORING ---
    sidebar_content.append(
        c.Div(class_name="mb-4", components=[
            c.Div(class_name="text-info small fw-bold mb-2", components=[c.Text(text="📟 TASK MONITOR")]),
            c.Div(class_name="rounded-3 border border-secondary border-opacity-20 bg-black bg-opacity-20 p-2", components=[
                c.Div(
                    class_name="d-flex justify-content-between align-items-center py-2 px-1 border-bottom border-secondary border-opacity-10",
                    components=[
                        c.Div(class_name="text-light small", components=[c.Text(text=f"ID:{p['id']}")]),
                        c.Div(
                            class_name=f"badge {'bg-success text-white' if p['status']=='Finished' else 'bg-warning text-dark'}",
                            components=[c.Text(text=p['status'])]
                        )
                    ]
                ) for p in processes
            ])
        ])
    )

    # --- Section: AGENT STATUS ---
    sidebar_content.append(
        c.Div(
            class_name="mt-auto p-3 rounded-3 bg-info bg-opacity-25 border border-info border-opacity-50",
            components=[
                c.Div(class_name="text-white small fw-bold", components=[c.Text(text="● SABR CORE ACTIVE")]),
                c.Div(class_name="text-info small mt-1", components=[c.Text(text="AiiDA v2.1 Syncing...")])
            ]
        )
    )

    return sidebar_content

def get_aiida_dashboard_layout(content: list[AnyComponent]) -> list[AnyComponent]:
    """
    Main layout with invalid style attributes removed.
    """
    return [
        c.PageTitle(text="SABR v2 | AiiDA Expert"),
        c.Navbar(
            title='SABR v2 | RESEARCH HUB',
            title_event=e.GoToEvent(url='/ui/'),
            class_name="sticky-top shadow-sm bg-white border-bottom border-info border-opacity-25",
        ),
        c.Div(
            class_name="container-fluid", 
            components=[
                c.Div(
                    class_name="row",
                    components=[
                        # Use `bg-dark` + `border-info` to emulate industrial dark styling.
                        c.Div(
                            class_name="col-md-3 vh-100 p-4 d-flex flex-column sticky-top bg-dark border-end border-info border-opacity-10",
                            components=get_aiida_sidebar() 
                        ),
                        # Main area.
                        c.Div(
                            class_name="col-md-9 bg-secondary bg-opacity-10 p-5 min-vh-100",
                            components=[
                                c.Div(
                                    class_name="bg-white p-5 rounded-4 shadow border border-info border-opacity-10",
                                    components=content
                                )
                            ]
                        ),
                    ]
                )
            ]
        )
    ]

# Keep remaining render helpers unchanged.
def get_chat_interface():
    return [
        c.Heading(text="Research Intelligence", level=2, class_name="mb-4 text-dark fw-bold"),
        c.ModelForm(model=AgentRequest, submit_url='/api/ui/chat'),
    ]

def render_sabr_response(data: SABRResponse):
    return [
        c.Heading(text="Analysis Result", level=2),
        c.Div(class_name="p-4 rounded-4 bg-info bg-opacity-5 border border-info border-opacity-20 mb-4", components=[
            c.Markdown(text=data.answer),
        ]),
        c.Details(label="Thought Log", content=[c.Paragraph(text=s) for s in data.thought_process])
    ]
