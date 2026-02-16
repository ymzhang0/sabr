SABR Framework
Sense | Act | Brain | Reflect

SABR is a modular Python framework designed for building autonomous AI agents through a strictly decoupled architecture. It separates environment perception, decision-making, and tool execution into distinct, protocol-driven components.

Core Concept
The framework orchestrates a control loop that abstracts the interaction between a Large Language Model (LLM) and complex external systems:

Perceptor: Observes the environment and normalizes data into a structured Observation.

Brain: A reasoning layer (e.g., Gemini, GPT) that processes observations to decide on an Action.

Executor: Routes actions to specific tools or executes dynamically generated code.

Reporter: Provides observability by logging the internal state and decision chain to multiple sinks (Console, Web UI, etc.).

Project Structure
The repository is organized into two main layers:

sab_core/: The hardware-agnostic core engine and base protocols.

engines/: Domain-specific implementations (e.g., engines/aiida for scientific data management).

Current Status
SABR is currently in the MVP (Minimum Viable Product) phase.

Core Engine: Fully asynchronous, supporting non-blocking execution loops.

Brain Integration: Implementation for Google Gemini 2.0 with native function calling support.

AiiDA Engine: A reference implementation for the AiiDA provenance database is included, featuring automated resource scanning (Archives/Profiles) and a Python code interpreter for complex data mining.

Web Interface: A NiceGUI-based dashboard for real-time monitoring and human-in-the-loop interaction.

Installation & Usage
1. Installation
Clone the repository and install in editable mode:

Bash
git clone https://github.com/your-username/sabr.git
cd sabr
pip install -e .
2. Basic Initialization
Python
from sab_core.engine import SABEngine
from sab_core.reporters.console import ConsoleReporter
from engines.aiida.perceptors.database import AIIDASchemaPerceptor
from engines.aiida.brain_factory import create_aiida_brain
from engines.aiida.executor import AiiDAExecutor

# 1. Initialize components
perceptor = AIIDASchemaPerceptor()
executor = AiiDAExecutor()
reporter = ConsoleReporter()

# 2. Build the brain with domain context
brain = create_aiida_brain(schema_info="Current database: production_v1")

# 3. Setup the engine
engine = SABEngine(
    perceptor=perceptor,
    brain=brain,
    executor=executor,
    reporters=[reporter]
)

# 4. Run the loop
await engine.run_once(intent="Analyze recent failed processes.")