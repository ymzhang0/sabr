# SABR v2: Standard Agent Bus for Research

SABR v2 is a next-generation AI agent framework designed for autonomous scientific discovery, specifically optimized for the **AiiDA** (Advanced Interactive Infrastructure for Data-Agnostic) ecosystem. 

Built on top of **PydanticAI**, SABR v2 transitions from linear execution to a **Cyclic Reasoning Graph**, enabling agents to self-diagnose failures and autocorrect simulation parameters in real-time.

## 🚀 Key Features

- **Cyclic Reasoning**: Powered by PydanticAI, the agent can loop through "Think-Tool-Observe" cycles to self-correct and retry failed tasks.
- **Strict Type Safety**: Every response is validated against Pydantic models, ensuring the UI always receives structured, reliable data.
- **Engine Decoupling**: The core bus (`sab_core`) is isolated from specific research engines (e.g., `aiida`), allowing for easy extension to other scientific tools like VASP or QE.
- **Oxford-Style UI**: A sophisticated, dark-themed dashboard built with **NiceGUI**, featuring a real-time thinking terminal and structured insights.

## 🏗️ Architecture

```text
sabr/
├── src/sab_core/        # Core Agent Bus (Generic logic & base classes)
├── engines/aiida/       # AiiDA Engine (Specialized agents, tools, & API)
├── app_api.py           # Backend Hub (FastAPI & Agent Orchestrator)
└── app_web.py           # Frontend UI (NiceGUI Dashboard)