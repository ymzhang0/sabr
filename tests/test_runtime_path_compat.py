from __future__ import annotations

from pathlib import Path


def test_legacy_runtime_paths_resolve_to_runtime_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_root = repo_root / "runtime"

    legacy_roots = (repo_root / "engines" / "aiida" / "data",)

    for legacy_root in legacy_roots:
        assert legacy_root.exists()
        assert legacy_root.resolve() == runtime_root.resolve()


def test_legacy_memory_directory_points_to_canonical_runtime_directory() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    canonical_memories = repo_root / "runtime" / "memories"
    legacy_memories = repo_root / "engines" / "aiida" / "data" / "memories"

    assert canonical_memories.exists()
    assert legacy_memories.exists()
    assert legacy_memories.resolve() == canonical_memories.resolve()
