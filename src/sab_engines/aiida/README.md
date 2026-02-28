# AiiDA Engine (Thin Client)

Current canonical runtime layout:

```text
src/sab_engines/aiida/
├── router.py          # Unified FastAPI routes (worker proxy + frontend API)
├── client.py          # Canonical bridge client facade
├── bridge_client.py   # Low-level HTTP request helpers
├── bridge_service.py  # Bridge snapshot/status service
├── service.py         # Service facade for hub/frontend helpers
├── frontend_bridge.py # Sync helpers for frontend bootstrap/process/context data
├── hub.py             # Worker-backed profile hub (remote profile source of truth)
├── deps.py            # Engine-specific dependency object
├── agent/
│   ├── researcher.py  # AiiDA researcher agent
│   └── tools.py       # All worker proxy tools (consolidated)
├── chat/
│   └── service.py     # Chat turn orchestration
├── schema.py          # Engine domain response models
├── config.py          # Engine settings (bridge URL, etc.)
├── static/            # Static assets
└── legacy/            # Archived legacy UI/API code (not mounted)
```

Compatibility paths removed:
- `engines/`
- `src/engines/`
- `src/sab_engines/aiida/agents/`
- `src/sab_engines/aiida/tools/`
- `src/sab_engines/aiida/api.py`
- `src/sab_engines/aiida/aiida_router.py`
