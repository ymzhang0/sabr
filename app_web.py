from nicegui import ui, app

# Import SABR v2 logic and UI components
from src.sab_engines.aiida.ui.legacy_nicegui.layout import create_aiida_layout
from src.sab_engines.aiida.ui.legacy_nicegui.controller import RemoteAiiDAController
from src.sab_core.memory.json_memory import JSONMemory

# --- 1. Global Configuration ---
API_URL = "http://localhost:8000"
# Global memory for UI states like recent archives
global_memory = JSONMemory(namespace="aiida_v2_ui")

# Serving static files for custom CSS/JS
# Note: Ensure src/sab_engines/aiida/static exists
app.add_static_files('/aiida/static', 'src/sab_engines/aiida/static')

# ============================================================
# 🎨 Main Page Entry
# ============================================================

@ui.page('/')
async def main():
    """
    Main entry point for the SABR-AiiDA web interface.
    Orchestrates the binding between the Oxford-style layout and 
    the PydanticAI-powered remote controller.
    """
    
    # 🚩 1. Initialize Layout
    # Pass available models defined in settings or defaults
    available_models = ["gemini-2.0-flash", "gemini-1.5-pro"]
    components = create_aiida_layout(
        theme_name='gemini_dark', 
        available_models=available_models
    )

    # 🚩 2. Initialize Remote Controller
    # This controller handles all Cyclic Reasoning logic via API
    ctrl = RemoteAiiDAController(
        api_url=API_URL, 
        components=components, 
        memory=global_memory
    )

    # 🚩 3. Core Event Bindings (Interaction Logic)

    # A. Sending Messages
    components['send_btn'].on('click', lambda: ctrl.handle_send())
    components['input'].on('keydown.enter', lambda: ctrl.handle_send())

    # B. Environment & File Management
    components['upload_btn'].on('click', ctrl.pick_local_file)
    
    # Handle Archive Switching
    # We use on_value_change to trigger the switch_context logic
    components['archive_select'].on_value_change(
        lambda e: ctrl.switch_context(e.value)
    )

    # C. Suggestion Cards (Shortcuts)
    # Bind each predefined suggestion card to a direct send action
    for card, intent in components['suggestion_cards']:
        card.on('click', lambda i=intent: ctrl.handle_send(preset_text=i))

    # D. Model Management
    # When user switches the Gemini model in the pulsing selector
    components['model_select'].on_value_change(
        lambda e: ui.notify(f"Brain switched to: {e.value}", type='info')
    )

    # 🚩 4. JavaScript Bridge (Node Inspection)
    # This listens to the 'node_clicked' event emitted by the JS 
    # injected in layout.py
    ui.on('node_clicked', lambda msg: ctrl.handle_node_inspection(msg))

    # 🚩 5. Post-Load Initialization
    # Load recent archive history from JSON memory on startup
    with components['archive_history']:
        ctrl._load_archive_history()

    # Define cleanup on shutdown
    app.on_shutdown(ctrl.close)

# ============================================================
# 🏁 Start Web Server
# ============================================================

if __name__ in {"__main__", "__mp_main__"}:
    # Run the UI on port 8080
    ui.run(
        port=8080, 
        title="SABR v2 | AiiDA Assistant",
        dark=True,
        # Ensure smooth animations
        reload=True 
    )
