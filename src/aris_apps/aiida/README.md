# AiiDA App (Canonical Path)

Current canonical app layout:

```text
src/aris_apps/aiida/
├── api/              # FastAPI assembly and root routes
├── agent/            # Researcher agent, prompts, and worker-backed tools
├── chat/             # Chat session orchestration and workspace state
├── presenters/       # Frontend-facing payload shaping
├── ui/               # Legacy NiceGUI compatibility surface
├── client.py         # Canonical worker client facade
├── bridge_client.py  # Low-level HTTP request helpers
├── bridge_service.py # Bridge snapshot/status service
├── service.py        # Service facade for hub/frontend helpers
├── frontend_bridge.py
├── hub.py
├── deps.py
├── config.py
├── schema.py
├── schemas.py
├── specializations.py
└── static/           # Canonical app static assets
```

Legacy compatibility imports remain under `src/sab_engines/aiida/` during the
ARIS transition, but new implementation work should land here.
