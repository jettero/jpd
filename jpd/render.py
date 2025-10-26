#!/usr/bin/env python
# coding: utf-8

# XXX: This is AI slop cuz I let codex do it fairly unsupervised. it 'works', but it's heinous to read.

import os
import re
import textwrap
from datetime import datetime, timezone
from tabulate import tabulate


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
    pri = incident.get("priority") or {}
    if isinstance(pri, dict):
        name = pri.get("name")
        if name:
            return f" [priority: {name}]"
    return ""


def assignee_tag(incident):
    assignments = incident.get("assignments") or []
    if not assignments:
        return ""
    a0 = assignments[0]
    u = a0.get("assignee") or {}
    uname = u.get("summary") or u.get("name") or u.get("email") or u.get("id")
    return f" [{uname}]" if uname else ""


def service_prefix(thing, show_service_info, incident_service_ref=None):
    if not show_service_info:
        return ""
    svc = thing.get("service") or {}
    # For alerts, suppress when same as incident service
    sid = svc.get("id") or svc.get("summary") or svc.get("name")
    if incident_service_ref is not None and sid == incident_service_ref:
        return ""
    sname = svc.get("summary") or svc.get("name") or ""
    return f"{sname}: " if sname else ""


def tag_safe_wrap(tw, text):
    # Protect bracketed tags from internal wrapping by swapping spaces for BEL
    guarded = re.sub(r"\[[^\]]+\]", lambda m: m.group(0).replace(" ", "\x07"), text)
    wrapped = tw.wrap(guarded) or [""]
    return [w.replace("\x07", " ") for w in wrapped]


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


def incidents_to_text(incidents, show_service_info=False, show_alerts=True):
    """Render incidents as a two-column plain text table.

    - Left column: ID
    - Right column: wrapped summary with status/priority/assignee (and optional team)
    - Respects terminal width via COLUMNS env (defaults to 80)
    - Avoids breaking words inside square brackets
    """
    cols = int(os.environ.get("COLUMNS", 80))
    id_width = 18
    gap = 2
    # Require at least 33 columns per user guidance
    min_cols = 33
    if cols < min_cols:
        raise ValueError("Display too narrow for text renderer")
    wrap_width = max(20, cols - id_width - gap)

    tw = textwrap.TextWrapper(
        width=wrap_width,
        break_long_words=False,
        break_on_hyphens=False,
        replace_whitespace=False,
    )

    rows: List[List[str]] = []

    for inc in incidents:
        iid = inc.get("id", "")
        st = inc.get("status", "")
        st_tag = status_tag(st)
        # age tag from created_at
        age_tag = ""
        created_at = inc.get("created_at") or inc.get("createdAt")
        if created_at:
            age_tag = f" [{format_timedelta_brief(created_at)}]"

        # priority
        pr = priority_tag(inc)

        # assignee (first)
        assignee = assignee_tag(inc)

        inc_service_ref = None
        if show_service_info:
            svc_dict = inc.get("service") or {}
            inc_service_ref = svc_dict.get("id") or svc_dict.get("summary")
        svc_part = service_prefix(inc, show_service_info)

        summary = inc.get("title") or inc.get("summary") or ""
        # In typical cases, the first alert repeats the incident summary. To reduce
        # redundancy, omit the incident summary text when showing alerts; otherwise include it.
        if show_alerts:
            text = f"{svc_part}{st_tag}{pr}{assignee}{age_tag}".strip()
        else:
            text = f"{svc_part}{summary} {st_tag}{pr}{assignee}{age_tag}".strip()

        # Guard spaces inside square-bracket tags to prevent wrapping within them.
        # Replace spaces inside [...] with BEL (\x07) before wrapping, then restore.
        wrapped = tag_safe_wrap(tw, text)
        rows.append([iid, wrapped[0]])
        for cont in wrapped[1:]:
            rows.append(["", cont])

        # Render alerts only if explicitly requested
        if show_alerts:
            alerts = inc.get("alerts") or []
            # Prepare safe delimiter-aware prefix for optional trimming
            incident_prefix = summary.strip()
            incident_prefix_lc = incident_prefix.lower()
            for al in alerts:
                # Only include alert service if explicitly requested AND it differs from incident service
                asvc_name = ""
                if show_service_info:
                    asvc = al.get("service") or {}
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
                if a_created_at:
                    aage_tag = f" [{format_timedelta_brief(a_created_at)}]"
                abits = f"{asvc_name}: {atitle_stripped}" if asvc_name else atitle_stripped
                abits = abits.strip()
                if not abits:
                    continue
                atext = f"• {abits} {ast_tag}{aage_tag}".strip()
                awrapped = tag_safe_wrap(tw, atext)
                rows.append(["", awrapped[0]])
                for cont in awrapped[1:]:
                    rows.append(["", cont])

    return tabulate(rows, tablefmt="plain", colalign=("left", "left"))
