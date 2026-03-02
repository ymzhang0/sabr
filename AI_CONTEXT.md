# SABR Architecture & Code Review Context

## Overview
This document serves as the context transfer for AI agents working across different machines, preserving the review of the SABR ("The Brain") architecture. SABR's primary responsibility is intent parsing, tool orchestration, and presentation, strictly separated from the physical computational environment.

## 1. Core Architecture: Brain-Body Split
SABR operates as the **Brain**. It communicates with the AiiDA-Worker (**Body**) entirely via REST APIs. 
**Review finding**: SABR mostly adheres to the "no AiiDA dependency" rule. However, local imports of `aiida` (e.g., `from aiida import orm` or `plugins`) exist inside certain functions within `src/sab_engines/aiida/presenters/workflow_view.py`. These act as fallbacks but are a slight violation of the strict boundary and should be monitored or refactored if full isolation is desired. HTTP transport is correctly encapsulated.

## 2. Key Design Patterns Analyzed

### Presenter Pattern (Demonstration Layer)
**Location:** `src/sab_engines/aiida/presenters/` (`node_view.py`, `workflow_view.py`)
**Implementation:** Takes raw JSON payloads returned by the Worker's API and recursively formats/ flattens them for the React frontend. It handles previews, link dereferencing, and stripping complex nested attributes into primitive JSON dictionaries.

### Bridge/Proxy Pattern
**Location:** `src/sab_engines/aiida/client.py`, `bridge_client.py`
**Implementation:** Wraps all `httpx` logic dynamically. It implements connection state caching, infrastructure introspection (counting codes/computers), connection offline awareness (`BridgeOfflineError`), and error payload normalization (`_extract_error_payload`).

### Registry Pattern (Agent Capability Growth)
**Location:** `src/sab_engines/aiida/agent/tools.py`, `researcher.py`
**Implementation:** SABR interacts with the Worker's `core.scripts` via `/registry/list` and `/registry/register`. The agent's LLM prompt explicitly instructs it to check for registered skills on startup. A registered tool dynamically receives AiiDA execution context on the worker.

### Observer Pattern (Streaming)
**Location:** `src/sab_engines/aiida/router.py` (SSE Streams), `deps.py` (`log_step`)
**Implementation:** `AiiDADeps.log_step` fires structured string messages into the execution context. The API router (`/stream/chat`, `/stream/logs`, `/stream/process`) serves these concurrent state changes to the frontend using Server-Sent Events (SSE), keeping UI non-blocking while complex reasoning steps execute.

## Data Flow
User -> Next.js Frontend -> FastAPI SABR Routers -> SABR Auto-Agent -> Tool Call -> `AiiDAWorkerClient` -> AiiDA-Worker REST API -> SABR Presenter -> SSE/JSON Frontend Render.

## 3. Frontend Architecture Insights
### Submission Review & Draft Builders
**Location:** `sabr/frontend/src/components/dashboard/submission-modal.tsx`
**Implementation:** The submission UI dynamically reads AiiDA Builder outputs. To support WorkChains (like `pwrelaxworkchain`), specific port parameters like `metadata.options` (e.g., `workdir`, `account`, `resources`) must be mapped deeply into nested calculation namespaces (e.g., `base.pw.metadata.options`) instead of the root directory. Furthermore, form state hooks relying on `metadata` or `inputs` (like global code inheritance) require stable references, avoiding immediate resets upon edits.
