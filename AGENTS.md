Notes for running tests in varied environments

- To avoid interference and run just this project's tests, disable auto-loading of external plugins when invoking pytest:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- This does not change test behavior; it simply prevents unrelated third-party plugins from being imported.

Additional agent notes from implementation/debugging

- Prefer robust CLI flags to avoid collisions:
  - Use `-f/--format` to switch output modes; keep JSON as default.
  - Reserve short flags used by subcommands (e.g., `-t` may be team-ids). If a global shortcut is needed, wire it at top level so it doesn’t conflict with subparser options.

- Text rendering approach for heterogeneous JSON:
  - Build a schema-light projection using commonly present PagerDuty fields (id, status, severity/priority, service summary, created_at, assignments, alerts).
  - Keep JSON output as the canonical view; make text mode opt-in.
  - For human-readable listings, compute a fixed-width left column (e.g., incident-id) and a wrapped message column based on `COLUMNS` env (default 80). Use `textwrap` with `break_long_words=False` and `break_on_hyphens=False` to preserve clickable URLs.
  - When measuring widths or aligning columns, strip ANSI escape codes first; never let them affect padding.

- Color output conventions:
  - Gate all color through a central helper with `--color {auto,always,never}`; default to `never` for predictable spacing in logs and redirects.
  - Only enable color automatically when stdout is a TTY in `auto` mode.

- HTML textification:
  - Use BeautifulSoup when available to turn HTML bodies into plain text. Provide a `--textify` flag; allow convenience shortcuts to enable it when entering human-readable modes.

- Bulk operations via keywords:
  - Allow intuitive keywords (e.g., `t|trig|triggered`, `a|all`) in place of identifiers to trigger bulk behavior.
  - Ensure `--dry-run` returns a clear, non-mutating plan (IDs and intended actions) rather than performing HTTP calls.

- Diagnostics/validation tips:
  - For formatting regressions, disable color (`--color=never`) and capture output to a file to inspect alignment and wrapping.
  - Use `COLUMNS` to stabilize width during development and tests.
