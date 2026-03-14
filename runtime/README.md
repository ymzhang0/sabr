Legacy runtime note for ARIS.

Mutable local state now lives under `~/.aris/`, including:
- chat and memory snapshots in `~/.aris/memories`
- uploads and caches under `~/.aris`
- generated script archives in `~/.aris/scripts`

Managed chat project roots now default to `~/.aris/projects`, and each project keeps
its per-session workspaces under `<project-root>/sessions/`.

Legacy paths under `runtime/`, `data/`, and `engines/aiida/data/` are still
supported during the migration window, but startup now migrates them into
`~/.aris/`.

This repository no longer keeps placeholder runtime subdirectories under
`runtime/`; only this note remains so the legacy path is documented.

Historical `.env` values that still point at the old repo-local runtime
directories are normalized back to `~/.aris/` during settings load so the
home-directory layout wins without breaking local startup scripts.
