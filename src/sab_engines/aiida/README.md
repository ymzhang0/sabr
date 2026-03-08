# AiiDA Engine (Legacy Compatibility Path)

`src/sab_engines/aiida/` is now a compatibility surface that forwards to the
canonical ARIS app path:

- `src/aris_apps/aiida/`

Legacy imports remain supported during the refactor so existing tests, scripts,
and runtime entrypoints do not break. New implementation work should move to
the canonical path.
