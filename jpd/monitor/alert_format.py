"""Rich-formatted rendering for one PagerDuty alert.

The shape of `body.details` varies wildly by integration (Grafana, LogScale,
custom webhooks, AI-generated notes, emails parsed into JSON). We don't try
to "understand" each — we walk the structure and apply visual rules that
work everywhere:

  - dict: render as `key: value` pairs with key styled cyan + bold
  - list: indent each item one level
  - PagerDuty CEF link shape (`{type: "link", href, text}`) → underlined
    text with the href shown dim afterward
  - PagerDuty CEF image shape (`{type: "image", src, alt?}`) → `[image] …`
  - any string that looks like a URL → cyan + underlined
  - any string containing HTML → textified via scan_for_html first
  - keywords {triggered, critical, error, warning, acknowledged, resolved,
    info, ok} get colored inline so they're easy to spot

The top-level metadata header (id, status, created_at, html_url, service)
is formatted in a key:value table at the top.
"""

import re

from rich.style import Style
from rich.text import Text

from jpd.monitor._log import get_logger


log = get_logger("alert_format")

_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_INDENT = "  "
_MAX_DEPTH = 8

_STATUS_COLORS = {
    "triggered": "bold red",
    "critical": "bold red",
    "error": "bold red",
    "warning": "yellow",
    "acknowledged": "green",
    "resolved": "green",
    "ok": "green",
    "info": "cyan",
}


def _link_style(href, color="cyan"):
    """OSC-8 hyperlink — iTerm2 / WezTerm / Kitty / Alacritty / etc render
    this as clickable, hiding the URL itself. Terminals without OSC-8
    support still get the colored+underlined visible text."""
    return Style(color=color, underline=True, link=href)


def format_alert(alert):
    """Return a Rich Text rendering for one alert dict."""
    out = Text()
    _render_header(out, alert)
    body = alert.get("body") or {}
    details = body.get("details") if isinstance(body, dict) else None
    contexts = body.get("contexts") if isinstance(body, dict) else None
    if details is not None:
        _section(out, "details")
        _render_value(out, details, indent=0)
        out.append("\n")
    if contexts:
        _section(out, "contexts")
        _render_value(out, contexts, indent=0)
        out.append("\n")
    return out


# -- header (id/status/etc.) ----------------------------------------------


def _render_header(out, alert):
    rows = []
    for k in ("id", "status", "urgency", "severity", "created_at"):
        v = alert.get(k)
        if v:
            rows.append((k, str(v)))
    svc = alert.get("service") or {}
    if svc.get("summary"):
        rows.append(("service", svc["summary"]))
    url = alert.get("html_url")
    if url:
        rows.append(("html_url", url))
    summary = alert.get("summary") or alert.get("title")
    if summary:
        rows.append(("summary", summary))

    if not rows:
        return
    key_w = max(len(k) for k, _ in rows)
    for k, v in rows:
        out.append(f"{k:<{key_w}}", style="bold cyan")
        out.append("  ")
        if k == "status":
            _append_status_token(out, v)
        elif k == "html_url" or _URL_RE.fullmatch(v):
            out.append(v, style=_link_style(v))
        else:
            _append_inline(out, v)
        out.append("\n")
    out.append("\n")


def _section(out, label):
    out.append(f"━━━ {label} ", style="dim")
    out.append("━" * max(1, 60 - len(label)), style="dim")
    out.append("\n")


# -- value rendering ------------------------------------------------------


def _render_value(out, value, indent=0):
    if indent >= _MAX_DEPTH:
        out.append(f"{_INDENT * indent}…\n", style="dim")
        return

    # PagerDuty CEF link shape — emit as a clickable OSC-8 hyperlink.
    if isinstance(value, dict) and value.get("type") == "link" and value.get("href"):
        out.append(_INDENT * indent)
        href = value["href"]
        text = value.get("text") or href
        out.append(text, style=_link_style(href))
        out.append("\n")
        return

    # PagerDuty CEF image shape — same trick; the marker stays visible
    # so it's obvious the link goes to an image not a page.
    if isinstance(value, dict) and value.get("type") == "image" and value.get("src"):
        out.append(_INDENT * indent)
        out.append("[image] ", style="magenta")
        alt = value.get("alt") or value.get("text") or "(image)"
        out.append(alt, style=_link_style(value["src"]))
        out.append("\n")
        return

    if isinstance(value, dict):
        if not value:
            out.append(f"{_INDENT * indent}{{}}\n", style="dim")
            return
        key_w = max((len(str(k)) for k in value.keys()), default=0)
        for k, v in value.items():
            out.append(_INDENT * indent)
            out.append(f"{str(k):<{key_w}}", style="bold cyan")
            out.append(": ")
            if _is_scalar(v):
                _append_inline(out, v)
                out.append("\n")
            else:
                out.append("\n")
                _render_value(out, v, indent=indent + 1)
        return

    if isinstance(value, list):
        if not value:
            out.append(f"{_INDENT * indent}[]\n", style="dim")
            return
        for i, item in enumerate(value):
            out.append(_INDENT * indent)
            out.append(f"[{i}] ", style="dim")
            if _is_scalar(item):
                _append_inline(out, item)
                out.append("\n")
            else:
                out.append("\n")
                _render_value(out, item, indent=indent + 1)
        return

    out.append(_INDENT * indent)
    _append_inline(out, value)
    out.append("\n")


def _is_scalar(v):
    return v is None or isinstance(v, (str, int, float, bool))


def _append_inline(out, v):
    """Append a scalar value with inline coloring (URLs, statuses, etc.)."""
    if v is None:
        out.append("null", style="dim italic")
        return
    if isinstance(v, bool):
        out.append("true" if v else "false", style="bold")
        return
    if isinstance(v, (int, float)):
        out.append(str(v), style="bright_white")
        return
    s = str(v)
    if not s:
        out.append("''", style="dim")
        return
    # Textify HTML before we render anything else.
    if s.lstrip().lower().startswith("<!doctype") or "<html" in s[:200].lower():
        from jpd.cmd import scan_for_html, HAS_BSOUP
        if HAS_BSOUP:
            try:
                s = scan_for_html(s)
            except Exception as e:
                log.debug("HTML textify failed: %s", e)

    # Multi-line strings: render with a leading newline and indented body.
    if "\n" in s:
        out.append("\n")
        for line in s.splitlines():
            out.append(f"{_INDENT}{line}\n")
        return

    # Walk inline, swapping URLs and status-tokens for colored fragments.
    _append_with_urls_and_tokens(out, s)


def _append_with_urls_and_tokens(out, s):
    pos = 0
    for m in _URL_RE.finditer(s):
        if m.start() > pos:
            _append_with_tokens(out, s[pos:m.start()])
        url = m.group(0)
        out.append(url, style=_link_style(url))
        pos = m.end()
    if pos < len(s):
        _append_with_tokens(out, s[pos:])


def _append_with_tokens(out, s):
    # Color status-like keywords case-insensitively at word boundaries.
    pattern = r"\b(" + "|".join(re.escape(k) for k in _STATUS_COLORS) + r")\b"
    pos = 0
    for m in re.finditer(pattern, s, flags=re.IGNORECASE):
        if m.start() > pos:
            out.append(s[pos:m.start()])
        _append_status_token(out, m.group(0))
        pos = m.end()
    if pos < len(s):
        out.append(s[pos:])


def _append_status_token(out, tok):
    style = _STATUS_COLORS.get(tok.lower(), "")
    if style:
        out.append(tok, style=style)
    else:
        out.append(tok)


def format_incident_summary(incident):
    """Header block for the IncidentScreen — the incident-level fields
    that aren't carried by any alert's text. Same visual style as the
    alert metadata header for consistency."""
    out = Text()
    rows = []
    rows.append(("id", incident.get("id") or "?"))
    if incident.get("status"):
        rows.append(("status", incident["status"]))
    if incident.get("urgency"):
        rows.append(("urgency", incident["urgency"]))
    pri = incident.get("priority")
    if isinstance(pri, dict) and pri.get("name"):
        rows.append(("priority", pri["name"]))
    svc = incident.get("service") or {}
    if svc.get("summary"):
        rows.append(("service", svc["summary"]))
    if incident.get("created_at"):
        rows.append(("created", incident["created_at"]))
    last_chg = incident.get("last_status_change_at")
    last_by = incident.get("last_status_change_by") or {}
    if last_chg:
        who = last_by.get("summary") if isinstance(last_by, dict) else None
        rows.append(("last change", f"{last_chg}  by {who}" if who else last_chg))
    assignments = incident.get("assignments") or ()
    if assignments:
        names = []
        for a in assignments:
            ass = a.get("assignee") if isinstance(a, dict) else None
            if isinstance(ass, dict):
                names.append(ass.get("summary") or ass.get("id") or "?")
        if names:
            rows.append(("assigned", ", ".join(names)))
    teams = incident.get("teams") or ()
    if teams:
        names = [t.get("summary") or t.get("id") for t in teams if isinstance(t, dict)]
        names = [n for n in names if n]
        if names:
            rows.append(("teams", ", ".join(names)))
    if incident.get("html_url"):
        rows.append(("html_url", incident["html_url"]))
    summary = incident.get("title") or incident.get("summary") or ""
    if summary:
        rows.append(("summary", summary))
    description = incident.get("description")
    if description and description != summary:
        rows.append(("description", description))

    key_w = max(len(k) for k, _ in rows) if rows else 0
    for k, v in rows:
        out.append(f"{k:<{key_w}}", style="bold cyan")
        out.append("  ")
        if k == "status":
            _append_status_token(out, v)
        elif k in ("html_url",) or _URL_RE.fullmatch(str(v)):
            out.append(str(v), style=_link_style(str(v)))
        else:
            _append_inline(out, v)
        out.append("\n")
    return out


def format_notes(notes):
    """Render incident notes as a Rich Text — one block per note, oldest
    first, with author + timestamp on a header line and the content
    indented underneath. URLs become OSC-8 links; status tokens get
    colorized. HTML payloads are textified."""
    out = Text()
    if not notes:
        out.append("(no notes)", style="dim italic")
        return out

    # PagerDuty returns notes newest-first by default; flip so the
    # conversation reads top-down chronologically.
    for note in reversed(list(notes)):
        author = "?"
        user = note.get("user")
        if isinstance(user, dict):
            author = user.get("summary") or user.get("name") or user.get("id") or "?"
        ts = note.get("created_at") or ""
        short = _short_ts(ts)
        out.append(short, style="bold yellow")
        out.append("  ")
        out.append(author, style="bold cyan")
        out.append("\n")
        content = note.get("content") or ""
        if content:
            _append_note_content(out, content)
        out.append("\n")
    return out


def _short_ts(iso):
    """'2026-06-06T13:33:31-04:00' -> '13:33'."""
    if not iso:
        return "--:--"
    s = iso.strip()
    # Tolerate Z and offsets; we just want HH:MM from the time portion.
    if "T" in s:
        time_part = s.split("T", 1)[1]
    else:
        time_part = s
    return time_part[:5] if len(time_part) >= 5 else time_part


def _append_note_content(out, content):
    """Run content through the same inline-coloring path as alert details
    (HTML textify, URL OSC-8 links, status token colorization)."""
    s = str(content)
    if s.lstrip().lower().startswith("<!doctype") or "<html" in s[:200].lower():
        from jpd.cmd import scan_for_html, HAS_BSOUP
        if HAS_BSOUP:
            try:
                s = scan_for_html(s)
            except Exception as e:
                log.debug("notes HTML textify failed: %s", e)
    for line in s.splitlines() or [""]:
        out.append(_INDENT)
        _append_with_urls_and_tokens(out, line)
        out.append("\n")
