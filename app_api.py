"""Compatibility entrypoint.

Canonical application wiring lives in `src.app_api`.
"""

from src.app_api import app


if __name__ == "__main__":
    import runpy

    runpy.run_module("src.app_api", run_name="__main__")
