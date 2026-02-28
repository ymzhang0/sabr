from sab_core.schema.action import Action

class ConsoleExecutor:
    def execute(self, action: Action) -> bool:
        if action.name == "no_op":
            print("[Executor] Status: OK.")
        else:
            msg = action.payload.get("message", "No message provided")
            print(f"[Executor] {action.name.upper()}: {msg}")
        return True