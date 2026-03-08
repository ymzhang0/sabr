from __future__ import annotations

from contextlib import suppress
from pathlib import Path

_REPO_ROOT = Path.cwd()
_LEGACY_RUNTIME_PATHS = (
    "default",
    "data/memories",
    "data/projects",
    "src/sab_engines/aiida/data/memories",
    "src/sab_engines/aiida/data/scripts",
    "engines/aiida/data/memories",
)


def _expand_exclude(raw_path: str) -> list[str]:
    cleaned = str(raw_path or "").strip().rstrip("/").rstrip("\\")
    if not cleaned:
        return []

    values = [cleaned]
    path = Path(cleaned)
    with suppress(ValueError):
        relative = path.relative_to(_REPO_ROOT).as_posix()
        if relative not in values:
            values.append(relative)

    expanded: list[str] = []
    for value in values:
        expanded.extend([value, f"{value}/*"])
    return expanded


def collect_reload_excludes(settings: object) -> list[str]:
    seen: set[str] = set()
    excludes: list[str] = []
    candidates = [
        getattr(settings, "ARIS_RUNTIME_ROOT", ""),
        getattr(settings, "ARIS_MEMORY_DIR", ""),
        getattr(settings, "ARIS_PROJECTS_ROOT", ""),
        getattr(settings, "ARIS_SCRIPT_ARCHIVE_DIR", ""),
        *_LEGACY_RUNTIME_PATHS,
    ]

    for candidate in candidates:
        for expanded in _expand_exclude(str(candidate)):
            if expanded in seen:
                continue
            seen.add(expanded)
            excludes.append(expanded)

    return excludes
