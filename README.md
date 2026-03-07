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
| `GET` | `/system/plugins` | List all installed AiiDA WorkChain/Calculation entry points. | `["core.arithmetic.add_multiply", "plugin_name.workflow_name", ...]` |
| `GET` | `/system/resources` | List available Computers and Codes. | `{"computers": [...], "codes": [...]}` |

### 2.2 Deep Introspection (Workflow Spec)
Used by the Agent to understand the "instruction manual" of a specific plugin.

* **Endpoint**: `GET /spec/{entry_point}`
* **Logic**: Recursively parses the `WorkChain` spec ports.
* **Payload Structure**:
    ```json
    {
      "entry_point": "plugin_name.workflow_name",
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

方案一：桌面端“伪装” (Electron) —— 最推荐

如果你希望在 Mac 或 Windows 桌面上有一个独立的图标，点开就是一个漂亮的窗口，Electron 是标准答案（VS Code、Slack 都是这么做的）。

做法：用 Electron 把你的前端项目包起来。它本质上是一个自带 Chromium 内核的容器。

优点：

零成本迁移：你现在的 Web 代码几乎不用改，直接塞进去就能跑。

系统集成：可以有自己的右键菜单、托盘图标（显示红绿灯状态）、系统原生通知。

离线缓存：可以把静态资源留在本地，启动速度比网页快得多。

挑战：它只是个“壳”，你的 aiida-worker 后端还是得在后台跑着（或者由 Electron 在启动时顺便拉起 Python 进程）。

方案二：VS Code 扩展 (First-class Citizen) —— 最专业

既然你已经在用 VS Code 开发，且代码就在 Workspace 里，为什么不把它做成一个 VS Code 插件？

做法：利用 VS Code 的 Webview API，把你现在的任务查看器集成到左侧侧边栏或独立面板。

优点：

沉浸式体验：你一边改代码，侧边栏直接看 AiiDA 任务进度，不用在浏览器和编辑器之间切来切去。

上下文关联：你可以实现“右键点击代码里的结构文件 -> 直接提交 AiiDA 任务”这种骚操作。

地位：对于计算化学/物理学家来说，VS Code 插件就是最强“App”。

方案三：跨平台移动端 (Flutter / React Native) —— 最极客

如果你想在手机上像刷朋友圈一样刷 AiiDA 任务，那就得走移动端开发路径。

做法：使用 React Native。由于你前端可能已经是 React 体系，迁移逻辑会顺手一些。

架构：

手机端：只负责显示和简单的指令发送（App）。

服务器端：你的 aiida-worker 挂在实验室服务器上，通过 API 与手机通信。

场景：躺在床上看计算收敛了没，收敛了就点一下手机屏幕，自动提交下一个任务。
