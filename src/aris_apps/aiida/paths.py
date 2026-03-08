from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    return Path(__file__).resolve().parent


def source_root() -> Path:
    return Path(__file__).resolve().parents[2]


def legacy_app_root() -> Path:
    return source_root() / "sab_engines" / "aiida"


def static_dir() -> Path:
    canonical = app_root() / "static"
    if canonical.is_dir():
        return canonical
    return legacy_app_root() / "static"


def logs_template() -> Path:
    canonical = static_dir() / "logs_template.html"
    if canonical.is_file():
        return canonical
    return legacy_app_root() / "static" / "logs_template.html"
