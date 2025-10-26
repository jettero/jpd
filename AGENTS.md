AGENTS guide (concise, actionable)

- Keep responses short; show code over prose.

Testing

- Run tests isolated from external plugins: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`.
- This only prevents third‑party plugin autoload; behavior is unchanged.

Text rendering

- Build a light projection from common PagerDuty fields: id, status, severity/priority, service summary, created_at, assignments, alerts.
- When listing things for the humans (--format text, etc); always try to align things  vertically
- a human's terminal is `os.environ.get('COLUMNS', 80)` wide
- Use `textwrap` with `break_long_words=False` and `break_on_hyphens=False` to preserve URLs.
- Do not allow word wrapping to break up markers like `[status: triggered]`)
