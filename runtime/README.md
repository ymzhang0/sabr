Canonical runtime root for the future ARIS layout.

Use this directory for mutable local state such as:
- chat and memory snapshots
- per-project session data
- uploads and caches
- generated script archives

Legacy paths under `data/` and `engines/aiida/data/` are still supported during
the migration window, but new runtime state should move here.

Historical `.env` values that still point at the old default data directories are
normalized back to `runtime/` during settings load so the canonical layout wins
without breaking local startup scripts.
