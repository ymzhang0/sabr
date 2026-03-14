# ARIS: Agentic Research Intelligence System

ARIS is an agentic scientific research framework built around a strict Brain/Body split and optimized for the AiiDA ecosystem. The current codebase evolved from a legacy implementation, but `aris_core` and `aris_apps` are now the canonical implementation surfaces.

The Brain-side repo lives in `aris/`. The worker remains a separate repo in `../aiida-worker`, with a separate Python environment and no direct code import dependency from ARIS into worker internals.

## Key Features

- Brain/Body split: ARIS orchestrates reasoning and UI workflows; AiiDA-Worker owns `aiida-core`, profiles, submissions, and database access.
- Typed integration boundary: worker responses are normalized into stable JSON payloads before they reach the frontend.
- Engine isolation: `aris_core` stays platform-level, while AiiDA-specific behavior lives under `aris_apps.aiida`.
- Runtime isolation: mutable memories, uploads, caches, and script archives live under `~/.aris/`, while managed chat projects default to `~/.aris/projects`.
## ARIS <-> AiiDA-Worker Protocol

The ARIS brain talks to AiiDA-Worker over HTTP/JSON. ARIS should not import worker Python modules directly.

### Base Configuration

- Protocol: `HTTP/1.1`
- Content type: `application/json`
- Default ARIS port: `8000`
- Default worker port: `8001`
- Authentication: trusted internal connection today; header-based auth can be layered on top later

### Root Compatibility Endpoints

These are the canonical root endpoints used by the current ARIS bridge:

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/status` | Worker status payload for bridge compatibility |
| `GET` | `/plugins` | Installed AiiDA workflow entry points |
| `GET` | `/system/info` | Profile, daemon, and environment summary |
| `GET` | `/resources` | Computers and codes visible to the worker |

### Submission Endpoints

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/submission/spec/{entry_point}` | Inspect normalized workflow input spec |
| `POST` | `/submission/validate` | Validate direct or protocol-driven workflow payloads |
| `POST` | `/submission/validate-job` | Validate job-style submission payloads |
| `POST` | `/submission/submit` | Submit direct workflow inputs or builder drafts |
| `POST` | `/submission/draft-builder` | Build a protocol-driven draft payload |
| `POST` | `/submission/submit-builder` | Submit a builder payload directly |
| `POST` | `/submission/generate-script` | Generate a submission script from a builder payload |

### Process and Data Endpoints

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/process/events` | SSE stream for live process updates |
| `GET` | `/process/{identifier}` | Process summary and provenance payload |
| `GET` | `/process/{identifier}/clone-draft` | Draft submission cloned from an existing process |
| `GET` | `/process/{identifier}/logs` | Process logs |
| `GET` | `/management/nodes/{pk}` | Generic node summary payload |
| `GET` | `/management/nodes/{pk}/script` | Script/archive payload for a node |
| `GET` | `/data/bands/{pk}` | Band structure plotting payload |
| `GET` | `/data/remote/{pk}/files` | Remote folder listing |
| `GET` | `/data/repository/{pk}/files` | Node repository listing |

### Registry and Management Endpoints

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/registry/list` | List registered analysis scripts |
| `POST` | `/registry/register` | Register or update a stored analysis script |
| `GET` | `/registry/workchains/{entry_point}/spec` | Alias for workflow spec inspection |
| `POST` | `/execute/{script_name}` | Execute a registered analysis script |
| `POST` | `/management/run-python` | Managed Python execution helper |
| `GET` | `/management/infrastructure` | Infrastructure summary for worker setup |
| `POST` | `/management/infrastructure/setup` | Provision infrastructure resources |

## Local Layout

- Canonical brain repo: `/Users/yimingzhang/Developer/aris-workspace/aris`
- Canonical worker repo: `/Users/yimingzhang/Developer/aris-workspace/aiida-worker`
- Canonical runtime root: `~/.aris`
- Default managed project root: `~/.aris/projects`

Backlog and product ideas should go in `/Users/yimingzhang/Developer/aris-workspace/aris/todo`, not in this README.

## Local Operations

- PM2 process names use the ARIS convention: `aris-api`, `aris-web`, `aris-tunnel`.
- The current PM2 ecosystem file lives at `/Users/yimingzhang/Developer/aris-workspace/aris/ecosystem.config.js`.
- Use `/Users/yimingzhang/Developer/aris-workspace/aris/scripts/pm2-dev.sh` for common local PM2 operations:
  `./scripts/pm2-dev.sh start`, `./scripts/pm2-dev.sh restart`, `./scripts/pm2-dev.sh status`, `./scripts/pm2-dev.sh logs web`, `./scripts/pm2-dev.sh startup`.
- The script defaults to the `dev` target, which manages `aiida-worker`, `aris-api`, and `aris-web` together. Use `core`, `api`, `worker`, or `web` when you want a narrower scope.
- `./scripts/pm2-dev.sh startup` writes a user-level `launchd` agent under `~/Library/LaunchAgents/` that runs `pm2 resurrect` on login. Run `./scripts/pm2-dev.sh save` after changing the managed process set.
- Legacy compatibility symlinks may still exist at `/Users/yimingzhang/Developer/aris` and `/Users/yimingzhang/Developer/aiida-worker` while local scripts are being updated.
- The Cloudflare tunnel defaults to `aris-aiida-tunnel`. If your deployed Cloudflare resource still has an older name, set `ARIS_TUNNEL_NAME` before starting PM2.
