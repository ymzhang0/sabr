# examples/aiida/tools/interpreter.py
import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr

def run_python_code(script: str):
    """执行 Python 脚本与 AiiDA 交互。AI 专用。"""
    exec_globals = {}
    try:
        from aiida import orm, plugins, engine
        exec_globals.update({"orm": orm, "plugins": plugins, "engine": engine})
    except ImportError:
        pass

    output_buffer = io.StringIO()
    try:
        with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
            exec(script, exec_globals)
        return output_buffer.getvalue() or "Code executed successfully (No output)."
    except Exception:
        return f"Error executing code:\n{traceback.format_exc()}"