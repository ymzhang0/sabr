# SABR v2: Standard Agent Bus for Research

SABR v2 is a next-generation AI agent framework designed for autonomous scientific discovery, specifically optimized for the **AiiDA** (Advanced Interactive Infrastructure for Data-Agnostic) ecosystem. 

Built on top of **PydanticAI**, SABR v2 transitions from linear execution to a **Cyclic Reasoning Graph**, enabling agents to self-diagnose failures and autocorrect simulation parameters in real-time.

## 🚀 Key Features

- **Cyclic Reasoning**: Powered by PydanticAI, the agent can loop through "Think-Tool-Observe" cycles to self-correct and retry failed tasks.
- **Strict Type Safety**: Every response is validated against Pydantic models, ensuring the UI always receives structured, reliable data.
- **Engine Decoupling**: The core bus (`sab_core`) is isolated from specific research engines (e.g., `aiida`), allowing for easy extension to other scientific tools like VASP or QE.
- **Oxford-Style UI**: A sophisticated, dark-themed dashboard built with **NiceGUI**, featuring a real-time thinking terminal and structured insights.

## 🏗️ SABR ⇌ AiiDA-Worker Communication Protocol (v1.0)

This protocol defines the communication standards between **SABR (Brain/Control)** and **AiiDA-Worker (Muscle/Execution)**. It follows a "Thin Client - Fat Server" architecture, ensuring that the Brain can orchestrate complex scientific workflows without having `aiida-core` installed locally.

---

## 1. Transport & Base Configuration
* **Protocol**: HTTP/1.1
* **Content-Type**: `application/json`
* **Ports**:
    * **SABR (Brain)**: `:8000`
    * **AiiDA-Worker (Bridge)**: `:8001`
* **Authentication**: Internal trusted connection (future support for `X-SABR-Token` headers).

---

## 2. Core API Endpoints

### 2.1 System & Environment Introspection
Used by the Brain to identify the state and capabilities of the current "Muscle" environment.

| Method | Path | Description | Example Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/system/status` | Fetch worker health, active profile, and daemon status. | `{"status": "online", "profile": "default", "daemon": "running"}` |
| `GET` | `/system/plugins` | List all installed AiiDA WorkChain/Calculation entry points. | `["quantumespresso.pw.relax", "vasp.vasp", ...]` |
| `GET` | `/system/resources` | List available Computers and Codes. | `{"computers": [...], "codes": [...]}` |

### 2.2 Deep Introspection (Workflow Spec)
Used by the Agent to understand the "instruction manual" of a specific plugin.

* **Endpoint**: `GET /spec/{entry_point}`
* **Logic**: Recursively parses the `WorkChain` spec ports.
* **Payload Structure**:
    ```json
    {
      "entry_point": "quantumespresso.pw.relax",
      "inputs": {
        "structure": { "type": "StructureData", "required": true, "help": "Input structure" },
        "parameters": { "type": "Dict", "required": false }
      },
      "outputs": { ... }
    }
    ```

### 2.3 Task Lifecycle
All validation and submission logic are closed-loop on the Worker side.

* **Validation**: `POST /submission/validate`
    * Accepts a full input dictionary; returns AiiDA's internal validation results.
* **Submission**: `POST /submission/submit`
    * The Brain sends parameters; the Worker handles `Code` loading, `DataNode` conversion, and executes `submit()`.

### 2.4 Monitoring & Data Extraction
Used by the Brain to fetch results and make high-level decisions.

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/process/{pk}` | Get process state and full hierarchical `ProcessTree`. |
| `GET` | `/process/{pk}/logs` | Extract stdout, stderr, and AiiDA report logs. |
| `GET` | `/data/node/{pk}` | Generic node serialization (JSON-safe). |
| `GET` | `/data/bands/{pk}` | Specialized extraction for BandStructure data. |

---

## 3. Error Handling

All APIs must follow standard HTTP status codes and return a consistent error structure:

```json
{
  "code": 400,
  "error": "InputValidationError",
  "message": "The key 'kpoints' is required but not provided.",
  "traceback": "..." 
}
```

## 4. Serialization Conventions (Dehydration)

To maintain a "Thin Client," the Worker must return "Dehydrated" JSON:

* **Node Identification**: All AiiDA objects (Code, Computer, Group) are referenced via PK (Integer) or UUID (String).

* **Type Flattening**: Complex AiiDA BaseType objects are automatically converted to native Python types (e.g., Float -> float).

* **Large Files**: Files under /data/remote are not transferred directly; the API returns file lists or provides streaming endpoints.

## 5. Implementation Roadmap

* **Worker Side**: Implement these paths using fastapi.APIRouter by reusing the migrated logic in the tools/ package.

* **SABR Side**: Maintain a BridgeClient that encapsulates these HTTP calls, providing clean methods like get_spec() and submit_job() for the Agent.