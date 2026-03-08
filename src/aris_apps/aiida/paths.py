from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    return Path(__file__).resolve().parent


def static_dir() -> Path:
    return app_root() / "static"


def logs_template() -> Path:
    return static_dir() / "logs_template.html"
