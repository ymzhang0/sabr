# engines/aiida/ui/fastui.py
from fastui import AnyComponent
from fastui import components as c
from fastui.components import forms as f
from fastui import events as e
from fastui import FastUI

SIDEBAR_SHELL = "col-md-3 vh-100 p-3 p-lg-4 d-flex flex-column border-end border-dark border-opacity-10 bg-white"
MAIN_SHELL = "col-md-9 vh-100 p-0 bg-white"
PANEL_BORDER = "border border-dark border-opacity-10 rounded-4 bg-white"
AIIDA_ICON_URL = "https://aiida.readthedocs.io/projects/aiida-core/en/stable/_images/aiida-icon.svg"

def get_process_panel(processes: list) -> list:
    """Render the latest process list."""
    if not processes:
        return [c.Div(class_name="text-muted small px-2 py-3", components=[c.Text(text="No recent processes.")])]

    items = []
    for p in processes:
        # Map AiiDA process state to display color.
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
                class_name="py-2 px-2 d-flex align-items-center gap-2 border-bottom border-dark border-opacity-10",
                components=[
                    # State indicator dot.
                    c.Div(class_name=f"small {dot_style}", components=[c.Text(text="●")]),
                    # Task metadata.
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
    Refactored sidebar with two entry paths:
    1) configured system profiles
    2) imported local archives
    """
    profiles_display = profiles_display or []
    processes = processes or []
    sidebar_content = []
    sidebar_content.append(
        c.Div(class_name=f"mb-4 mt-2 px-3 py-3 {PANEL_BORDER}", components=[
            c.Div(class_name="text-dark fw-bold mb-1", components=[c.Text(text="SABR")]),
            c.Div(class_name="text-muted small", components=[c.Text(text="AiiDA Expert")]),
        ])
    )

    # --- Header: Profile + Icon Button ---
    sidebar_content.append(
        c.Div(
            class_name="d-flex justify-content-between align-items-center mb-3 mt-1 px-2",
            components=[
                c.Div(
                    class_name="text-dark fw-semibold opacity-50 small",
                    components=[c.Text(text="PROFILE")]
                ),
                # Icon-only import button.
                c.Link(
                    components=[c.Text(text="📂")],
                    on_click=e.GoToEvent(url='/aiida/archives/browse-local'),
                    class_name="btn btn-sm rounded-3 p-1 border border-dark border-opacity-10 shadow-none text-dark",
                )
            ]
        )
    )
    # --- Render profile list (configured + imported) ---
    for profile_name, display_name, is_active in profiles_display:
        # Indicator color: green (active) vs gray (inactive).
        dot_color = "bg-success" if is_active else "bg-secondary opacity-25"
        

        sidebar_content.append(
            c.Link(
                components=[
                    c.Div(
                        # Darken background for active entries.
                        class_name=(
                            "py-2 px-3 mb-2 rounded-3 d-flex align-items-center gap-2 border border-dark border-opacity-10 "
                            f"{'bg-body-tertiary' if is_active  else 'bg-white'}"
                        ),
                        components=[
                            c.Div(
                                # Use compact padding and rounded-circle to render a dot.
                                class_name=f"rounded-circle {dot_color} p-1 d-inline-block",
                                components=[]  # Required; Pydantic expects a list.
                            ),
                            # Display label.
                            c.Div(
                                class_name=f"small {'fw-semibold text-black' if is_active else 'text-dark'}",
                                components=[c.Text(text=display_name)]
                            )
                        ]
                    )
                ],
                on_click=e.GoToEvent(url=f'/aiida/profiles/switch/{profile_name}'),
                class_name="text-decoration-none"
            )
        )
    # Insert live process panel area.
    sidebar_content.append(
        c.Div(class_name=f"mt-4 px-2 py-3 {PANEL_BORDER}", components=[
            c.Div(
                class_name="text-dark fw-semibold opacity-75 small uppercase mb-2", 
                components=[c.Text(text="Recent Tasks")]
            ),
            c.ServerLoad(
                path='/aiida/processes/stream',
                sse=True,
                sse_retry=3000,
                components=get_process_panel(processes)
            )
        ])
    )
    return sidebar_content

def get_aiida_dashboard_layout(
    content: list[AnyComponent], 
    profiles_display: list = None, 
    processes: list = None) -> list[AnyComponent]:
    """
    Claude-inspired layout: ivory-gray background with white rounded cards.
    """
    return FastUI([
        c.PageTitle(text="SABR | Claude Style"),
        c.Div(
            # `bg-body-tertiary` gives a neutral warm gray between `light` and `secondary`.
            class_name="container-fluid bg-body-tertiary vh-100 p-0", 
            components=[
                c.Div(
                    class_name="row g-0 h-100", 
                    components=[
                        # Sidebar.
                        c.Div(
                            class_name=SIDEBAR_SHELL,
                            components=get_aiida_sidebar(profiles_display=profiles_display, processes=processes)
                        ),
                        # Main content.
                        c.Div(
                            class_name=MAIN_SHELL,
                            components=content
                        ),
                    ]
                )
            ]
        )
    ])

def get_chat_messages_panel(chat_history: list[dict[str, str]]) -> list[AnyComponent]:
    if not chat_history:
        return [
            c.Div(
                class_name="h-100 d-flex align-items-center justify-content-center text-center",
                components=[
                    c.Div(
                        class_name="px-3",
                        components=[
                            c.Heading(text="Hi, where should we start?", level=2, class_name="fw-light text-dark opacity-75 mb-2"),
                            c.Paragraph(
                                text="Ask anything about your AiiDA archive.",
                                class_name="text-muted mb-0",
                            ),
                        ],
                    )
                ],
            )
        ]

    grouped: list[dict] = []
    for message in chat_history:
        raw_role = str(message.get("role", "")).strip().lower()
        status = str(message.get("status", "")).strip().lower()
        text = str(message.get("text", ""))
        turn_id = message.get("turn_id")

        is_assistant = raw_role in {"assistant", "ai", "model"} or status in {"thinking", "done", "error"}
        if not is_assistant:
            grouped.append({"kind": "user", "text": text, "turn_id": turn_id})
            continue

        if status == "thinking":
            grouped.append(
                {
                    "kind": "assistant",
                    "turn_id": turn_id,
                    "thinking": text,
                    "answer": None,
                    "answer_status": None,
                }
            )
            continue

        target = None
        if turn_id is not None:
            for item in reversed(grouped):
                if item.get("kind") == "assistant" and item.get("turn_id") == turn_id and item.get("answer") is None:
                    target = item
                    break
        if target is None:
            target = {
                "kind": "assistant",
                "turn_id": turn_id,
                "thinking": None,
                "answer": None,
                "answer_status": None,
            }
            grouped.append(target)

        target["answer"] = text
        target["answer_status"] = status or "done"

    rows: list[AnyComponent] = []
    for item in grouped:
        if item.get("kind") == "user":
            rows.append(
                c.Div(
                    class_name="row mb-3",
                    components=[
                        c.Div(
                            class_name="col-12 col-lg-11 col-xl-10 ms-auto ml-auto text-end text-right",
                            components=[
                                c.Div(
                                    class_name="d-inline-block float-end float-right px-3 py-2 rounded-4 "
                                    "bg-primary text-white border border-primary shadow-sm text-break",
                                    components=[c.Markdown(text=item.get("text", ""))],
                                )
                            ],
                        )
                    ],
                )
            )
            continue

        ai_avatar = c.Div(
            class_name="rounded-circle bg-white d-flex align-items-center justify-content-center "
            "border border-dark border-opacity-10 shadow-sm p-1 mt-1 flex-shrink-0",
            components=[
                c.Image(
                    src=AIIDA_ICON_URL,
                    alt="AiiDA",
                    width=22,
                    height=22,
                    loading="eager",
                )
            ],
        )

        assistant_body: list[AnyComponent] = []
        thinking_text = item.get("thinking")
        if thinking_text:
            assistant_body.append(
                c.Div(
                    class_name="small text-secondary py-1",
                    components=[c.Text(text=str(thinking_text))],
                )
            )

        answer_text = item.get("answer")
        if answer_text:
            answer_status = str(item.get("answer_status") or "done")
            answer_bubble = (
                "d-inline-block px-3 py-2 rounded-4 bg-danger-subtle text-danger-emphasis "
                "border border-danger-subtle shadow-sm text-break"
                if answer_status == "error"
                else "d-inline-block px-3 py-2 rounded-4 bg-light border border-dark border-opacity-10 text-dark shadow-sm text-break"
            )
            assistant_body.append(
                c.Div(
                    class_name=answer_bubble,
                    components=[c.Markdown(text=str(answer_text))],
                )
            )

        if not assistant_body:
            continue

        rows.append(
            c.Div(
                class_name="row mb-3",
                components=[
                    c.Div(
                        class_name="col-12 col-lg-11 col-xl-10",
                        components=[
                            c.Div(
                                class_name="row g-2",
                                components=[
                                    c.Div(class_name="col-auto", components=[ai_avatar]),
                                    c.Div(
                                        class_name="col",
                                        components=[
                                            c.Div(
                                                class_name="d-flex flex-column gap-1",
                                                components=assistant_body,
                                            )
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            )
        )
    return [
        c.Div(
            class_name="h-100 d-flex flex-column",
            components=rows,
        )
    ]


def get_chat_interface(
    chat_history: list[dict[str, str]] | None = None,
    model_name: str | None = None,
    available_models: list[str] | None = None,
    quick_shortcuts: list[dict[str, str]] | None = None,
):
    chat_history = chat_history or []
    available_models = available_models or ["gemini-2.0-flash"]
    quick_shortcuts = quick_shortcuts or []
    model_name = model_name if model_name in available_models else available_models[0]
    model_options = [{"value": m, "label": m} for m in available_models]

    return [
        c.Div(
            class_name="d-flex flex-column vh-100 bg-white",
            components=[
                c.Div(
                    class_name="flex-grow-1 d-flex flex-column p-3 p-lg-4 overflow-hidden",
                    components=[
                        c.Div(
                            class_name="flex-grow-1 overflow-auto px-2 px-lg-4 pt-2 pb-3",
                            components=[
                                c.Div(class_name="mx-auto h-100", components=[
                                    c.ServerLoad(
                                        path="/aiida/chat/messages/stream",
                                        sse=True,
                                        sse_retry=1200,
                                        components=get_chat_messages_panel(chat_history),
                                    )
                                ]),
                            ],
                        )
                    ],
                ),
                c.Div(
                    class_name="flex-shrink-0 px-3 px-lg-4 pb-4 pt-2 bg-white border-top border-dark border-opacity-10",
                    components=[
                        c.Div(
                            class_name="mx-auto",
                            components=[
                                c.Div(
                                    class_name="d-flex flex-wrap gap-2 mb-2",
                                    components=[
                                        c.Button(
                                            text=item["label"],
                                            on_click=e.GoToEvent(url=item["url"]),
                                            class_name="btn btn-sm btn-light border border-dark border-opacity-10 rounded-pill px-3",
                                        )
                                        for item in quick_shortcuts
                                    ],
                                ),
                                c.Form(
                                    submit_url='/api/aiida/chat',
                                    display_mode="page",
                                    class_name="bg-white border border-dark border-opacity-10 rounded-4 px-3 pt-3 pb-2 p-lg-4 shadow-sm",
                                    form_fields=[
                                        f.FormFieldTextarea(
                                            name="intent",
                                            title=" ",
                                            rows=3,
                                            placeholder="Message SABR...",
                                            class_name="mb-1 mt-0 border-0 shadow-none bg-transparent",
                                        ),
                                    ],
                                    footer=[
                                        c.Div(
                                            class_name="d-flex justify-content-between align-items-end pt-2",
                                            components=[
                                                c.Div(
                                                    class_name="d-flex align-items-end gap-1",
                                                    components=[
                                                        c.Link(
                                                            components=[c.Text(text="Clear chat")],
                                                            on_click=e.GoToEvent(url='/aiida/chat/clear'),
                                                            class_name="small text-decoration-none text-secondary pb-1",
                                                        ),
                                                        c.Div(
                                                            class_name="w-25",
                                                            components=[
                                                                f.FormFieldSelect(
                                                                    name="model_name",
                                                                    title="",
                                                                    options=model_options,
                                                                    initial=model_name,
                                                                    vanilla=True,
                                                                    multiple=False,
                                                                    class_name="mb-0 border-0 shadow-none bg-transparent form-select-sm",
                                                                    placeholder="Model",
                                                                ),
                                                            ],
                                                        ),
                                                    ],
                                                ),
                                                c.Button(
                                                    text="Send",
                                                    html_type="submit",
                                                    class_name="btn btn-dark rounded-pill px-4 py-2 fw-semibold",
                                                ),
                                            ],
                                        )
                                    ],
                                )
                            ],
                        )
                    ],
                ),
            ],
        )
    ]

def render_explorer(profiles: list, archives: list):
    """
    Dual-panel explorer:
    AiiDA profiles on top, local archive files at the bottom.
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
                    # Optional: add a dedicated "Load" action button here.
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
