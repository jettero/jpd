#!/usr/bin/env python
# coding: utf-8

# XXX: This is AI slop cuz I let codex do it fairly unsupervised. it 'works', but it's heinous to read.

import os
import sys
import re
from datetime import datetime, timezone
from tabulate import tabulate

INCIDENT_SYMBOL = '*'
ALERT_SYMBOL = '>'


def format_timedelta_brief(created_at):
    """Return a compact age from ISO8601 input like 2h5m, 3m10s, 45s.

    - Accepts an ISO8601 string ("...Z" or with offset). None/parse errors => "0s".
    - Computes now in UTC, ensures non-negative.
    - Includes at most the two most-significant non-zero units.
    - Units: d, h, m, s.
    """
    try:
        if not created_at:
            total = 0
        else:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            total = int(delta.total_seconds())
            if total < 0:
                total = 0
    except Exception:
        total = 0

    days = total // 86400
    rem = total % 86400
    hours = rem // 3600
    rem %= 3600
    minutes = rem // 60
    secs = rem % 60

    ordered: list[str] = []
    if days:
        ordered.append(f"{days}d")
    if hours:
        ordered.append(f"{hours}h")
    if minutes:
        ordered.append(f"{minutes}m")
    if secs or not ordered:
        ordered.append(f"{secs}s")
    return "".join(ordered[:2])


def status_tag(val):
    return f"[{val}]" if val else ""


def priority_tag(incident):
    pri = incident.get("priority", {})
    if isinstance(pri, dict):
        name = pri.get("name")
        if name:
            return f" [priority: {name}]"
    return ""


def assignee_tag(incident):
    assignments = incident.get("assignments", [])
    if not assignments:
        return ""
    a0 = assignments[0]
    u = a0.get("assignee", {})
    uname = u.get("summary") or u.get("name") or u.get("email") or u.get("id")
    return f" [{uname}]" if uname else ""


def service_prefix(thing, show_service_info, incident_service_ref=None):
    if not show_service_info:
        return ""
    svc = thing.get("service", {})
    # For alerts, suppress when same as incident service
    sid = svc.get("id") or svc.get("summary") or svc.get("name")
    if incident_service_ref is not None and sid == incident_service_ref:
        return ""
    sname = svc.get("summary") or svc.get("name") or ""
    return f"{sname}: " if sname else ""


def tag_safe_tabulate(rows, **tab_kwargs):
    tag_db = dict()

    def _compute_tag_replacement(m):
        x = m.group(0)
        try:
            return tag_db[x]
        except KeyError:
            pass
        inside = x[1:-1]
        if re.search(r'[^A-Za-z0-9]', inside):
            c = len(tag_db) + 7
            tag_db[x] = gtxt = f'[\x07{c:03d}]'
            return gtxt
        return x

    def _fixup_tag_replacement(m):
        x = m.group(0)
        try:
            return tag_db[x]
        except KeyError:
            pass
        return x

    for row in rows:
        row[2] = re.sub(r'\[[^\]]{4,}\]', _compute_tag_replacement, row[2])

    rendered = tabulate(rows, **tab_kwargs)

    tag_db = {v: k for k,v in tag_db.items()}
    rendered = re.sub(r'\[\x07\d+\]', _fixup_tag_replacement, rendered)

    return rendered


def strip_incident_prefix(alert_title, incident_summary):
    if not alert_title or not incident_summary:
        return alert_title
    tlc = alert_title.lower()
    pref = incident_summary.strip().lower()
    if not tlc.startswith(pref):
        return alert_title
    rest = alert_title[len(incident_summary.strip()) :]
    if rest[:2] in (": ", " -", " –", " —") or (rest[:1] in (":", "-", "–", "—", "|", "\t", " ")):
        return rest.lstrip(" -:|\t")
    return alert_title


def _should_color(color_opt):
    if color_opt == "always":
        return True
    if color_opt == "never":
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def _colorize_text(rendered, enable):
    if not enable:
        return rendered
    # Simple tag matching post-tabulation to avoid breaking wraps
    def repl_status(m):
        txt = m.group(0)
        if txt == "[acknowledged]":
            return "\x1b[32m" + txt + "\x1b[0m"  # green
        if txt == "[triggered]":
            return "\x1b[31m" + txt + "\x1b[0m"  # red
        return "\x1b[36m" + txt + "\x1b[0m"      # cyan for other [tags]

    import re
    # colorize status/other tags
    rendered = re.sub(r"\[[^\]]+\]", repl_status, rendered)
    # colorize priority tags like [P1], [P2] as purple (magenta)
    rendered = re.sub(r"\[P[1-9]\]", lambda m: "\x1b[35m" + m.group(0) + "\x1b[0m", rendered)
    # colorize time-like [7h35m] specifically to brown (use yellow as approx)
    rendered = re.sub(r"\[(?:\d+[smhd])+\]", lambda m: "\x1b[33m" + m.group(0) + "\x1b[0m", rendered)
    return rendered


def incidents_to_text(incidents, show_service_info=False, show_alerts=True, color="auto"):
    """Render incidents as a two-column plain text table.

    - Left column: ID
    - Right column: wrapped summary with status/priority/assignee (and optional team)
    - Respects terminal width via COLUMNS env (defaults to 80)
    - Avoids breaking words inside square brackets
    """
    id_width = 14
    gap = 2
    emoji_width = 1
    spaces_between_columns = 2
    summary_width = int(os.environ.get("COLUMNS", 80)) - (id_width + emoji_width + 2*spaces_between_columns)

    if summary_width < 30:
        raise ValueError("Display too narrow for text renderer")

    rows = []

    for inc in incidents:
        iid = inc.get("id", "")
        st = inc.get("status", "")
        st_tag = status_tag(st)
        # age tag from created_at
        age_tag = ""
        created_at = inc.get("created_at") or inc.get("createdAt")
        if created_at:
            age_tag = f"[{format_timedelta_brief(created_at)}]"

        # priority
        pr = priority_tag(inc)

        # assignee (first)
        assignee = assignee_tag(inc)

        inc_service_ref = None
        if show_service_info:
            svc_dict = inc.get("service", {})
            inc_service_ref = svc_dict.get("id") or svc_dict.get("summary")
        svc_part = service_prefix(inc, show_service_info)

        summary = inc.get("title") or inc.get("summary") or ""
        # In typical cases, the first alert repeats the incident summary. To reduce
        # redundancy, omit the incident summary text when showing alerts; otherwise include it.
        if show_alerts:
            text = f"{svc_part}{st_tag}{pr}{assignee}{age_tag}"
        else:
            text = f"{svc_part}{summary} {st_tag}{pr}{assignee}{age_tag}"

        rows.append([iid, INCIDENT_SYMBOL, text])

        # Render alerts only if explicitly requested
        if show_alerts:
            alerts = inc.get("alerts", [])
            # Prepare safe delimiter-aware prefix for optional trimming
            incident_prefix = summary.strip()
            incident_prefix_lc = incident_prefix.lower()
            for al in alerts:
                # Only include alert service if explicitly requested AND it differs from incident service
                asvc_name = ""
                if show_service_info:
                    asvc = al.get("service", {})
                    alert_service_ref = asvc.get("id") or asvc.get("summary") or asvc.get("name")
                    if alert_service_ref and alert_service_ref != inc_service_ref:
                        asvc_name = asvc.get("summary") or asvc.get("name") or ""
                atitle = al.get("title") or al.get("summary") or ""
                atitle_stripped = strip_incident_prefix(atitle, incident_prefix)
                # alert status
                ast = al.get("status", "")
                ast_tag = status_tag(ast)
                # alert age from created_at
                aage_tag = ""
                a_created_at = al.get("created_at") or al.get("createdAt")
                if a_created_at: # XXX prefixing with spaces:
                    aage_tag = f"[{format_timedelta_brief(a_created_at)}]"
                abits = f"{asvc_name}: {atitle_stripped}" if asvc_name else atitle_stripped
                abits = abits.strip()
                if not abits:
                    continue
                atext = f"{abits} {ast_tag}{aage_tag}".strip()
                rows.append(["", ALERT_SYMBOL, atext])

    ##### start of special guard for stupid dumbdumb heads -- do not remove
    for row in rows:
        if len(row) != 3:
            raise Exception("I'm a stupid dumb dumb head")
        for item in row:
            if not isinstance(item, str):
                raise Exception("I'm a stupid dumb dumb head")
            if item.startswith(" ") or item.endswith(" "):
                raise Exception("I'm a stupid dumb dumb head")
    ##### end of special guard for stupid dumbdumb heads -- do not remove

    # No rows? Avoid tabulate() IndexError and show a friendly message.
    if not rows:
        return "All clear??"

    rendered = tag_safe_tabulate(
        rows,
        tablefmt="plain",
        maxcolwidths=[None, None, summary_width],
    )
    # apply colors after tabulation/wrapping
    return _colorize_text(rendered, _should_color(color))
