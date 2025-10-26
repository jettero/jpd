# AGENTS guide (concise, actionable)

## Critical Importance

- Keep responses short; show code over prose.
- do not use getattr/hasattr and try/except blocks unless it really can't be avoided
- if you already know an instance has certain attributes because of it's type, then don't check for the attributes
- you must ask permission to use getattr/hasattr

## Style concerns
- do not use the fancy new type hinting. Pretend this is python 3.6 or whatever.

## Testing

- Run tests isolated from external plugins: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`.
- This only prevents third‑party plugin autoload; behavior is unchanged.
- be sure to use `@pytest.fixture` markers on test data and locate fixtures in t/confest.py
- try to re-use the fixtures as much as you can rather than always creating new ones.

## Text rendering

- Build a light projection from common PagerDuty fields: id, status, severity/priority, service summary, created_at, assignments, alerts.
- When listing things for the humans (--format text, etc); always try to align things  vertically
- a human's terminal is `os.environ.get('COLUMNS', 80)` wide
- Use `textwrap` with `break_long_words=False` and `break_on_hyphens=False` to preserve URLs.
- Do not allow word wrapping to break up markers like `[status: triggered]`)
