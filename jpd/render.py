#!/usr/bin/env python
# coding: utf-8

# XXX: This is AI slop cuz I let codex do it fairly unsupervised. it 'works', but it's heinous to read.

import os
import re
import textwrap
from typing import Iterable, List, Dict, Any
from datetime import datetime, timezone
from tabulate import tabulate


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
        status_tag = f"[{st}]" if st else ""
        # age tag from created_at
        age_tag = ""
        created_at = inc.get("created_at") or inc.get("createdAt")
        if created_at:
            try:
                # Expecting ISO8601; handle Z and offsets
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                delta = now - dt
                # Ensure non-negative
                if delta.total_seconds() < 0:
                    total = 0
                else:
                    total = int(delta.total_seconds())
                days = total // 86400
                rem = total % 86400
                hours = rem // 3600
                rem %= 3600
                minutes = rem // 60
                seconds = rem % 60
                parts: list[str] = []
                if days:
                    parts.append(f"{days}d")
                if hours:
                    parts.append(f"{hours}h")
                if minutes:
                    parts.append(f"{minutes}m")
                if seconds or not parts:
                    parts.append(f"{seconds}s")
                # Only most significant two non-zero (or one, if others zero)
                # Build ordered list and then trim
                ordered = []
                if days:
                    ordered.append(f"{days}d")
                if hours:
                    ordered.append(f"{hours}h")
                if minutes:
                    ordered.append(f"{minutes}m")
                if seconds or not ordered:
                    ordered.append(f"{seconds}s")
                age_str = "".join(ordered[:2])
                age_tag = f" [{age_str}]"
            except Exception:
                age_tag = ""

        # priority
        pr = ""
        pri = inc.get("priority") or {}
        if isinstance(pri, dict):
            name = pri.get("name")
            if name:
                pr = f" [priority: {name}]"

        # assignee (first)
        assignee = ""
        assignments = inc.get("assignments") or []
        if assignments:
            a0 = assignments[0]
            u = a0.get("assignee") or {}
            uname = u.get("summary") or u.get("name") or u.get("email") or u.get("id")
            if uname:
                assignee = f" [{uname}]"

        if show_service_info:
            service = inc.get("service") or {}
            svc = service.get("summary") or service.get("name") or ""
            svc_part = f"{svc}: " if svc else ""
        else:
            svc_part = ""

        summary = inc.get("title") or inc.get("summary") or ""
        # In typical cases, the first alert repeats the incident summary. To reduce
        # redundancy, omit the incident summary text when showing alerts; otherwise include it.
        if show_alerts:
            text = f"{svc_part}{status_tag}{pr}{assignee}{age_tag}".strip()
        else:
            text = f"{svc_part}{summary} {status_tag}{pr}{assignee}{age_tag}".strip()

        # Guard spaces inside square-bracket tags to prevent wrapping within them.
        # Replace spaces inside [...] with BEL (\x07) before wrapping, then restore.
        text_for_wrap = re.sub(r"\[[^\]]+\]", lambda m: m.group(0).replace(" ", "\x07"), text)

        wrapped = tw.wrap(text_for_wrap) or [""]
        # Restore BEL placeholders back to regular spaces.
        wrapped = [w.replace("\x07", " ") for w in wrapped]
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
                asvc = al.get("service") or {}
                asvc_name = ""
                if show_service_info:
                    inc_service = (inc.get("service") or {}).get("id") or (inc.get("service") or {}).get("summary")
                    alert_service = asvc.get("id") or asvc.get("summary") or asvc.get("name")
                    if alert_service and alert_service != inc_service:
                        asvc_name = asvc.get("summary") or asvc.get("name") or ""
                atitle = al.get("title") or al.get("summary") or ""
                # Remove leading incident summary only when followed by delimiter
                atitle_stripped = atitle
                if incident_prefix_lc and atitle:
                    tlc = atitle.lower()
                    pref = incident_prefix_lc
                    if tlc.startswith(pref):
                        rest = atitle[len(incident_prefix) :]
                        if rest[:2] in (": ", " -", " –", " —") or (rest[:1] in (":", "-", "–", "—", "|", "\t", " ")):
                            atitle_stripped = rest.lstrip(" -:|\t")
                # alert status
                ast = al.get("status", "")
                ast_tag = f"[{ast}]" if ast else ""
                # alert age from created_at
                aage_tag = ""
                a_created_at = al.get("created_at") or al.get("createdAt")
                if a_created_at:
                    try:
                        dt = datetime.fromisoformat(a_created_at.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        delta = now - dt
                        total = int(delta.total_seconds()) if delta.total_seconds() >= 0 else 0
                        days = total // 86400
                        rem = total % 86400
                        hours = rem // 3600
                        rem %= 3600
                        minutes = rem // 60
                        seconds = rem % 60
                        ordered = []
                        if days:
                            ordered.append(f"{days}d")
                        if hours:
                            ordered.append(f"{hours}h")
                        if minutes:
                            ordered.append(f"{minutes}m")
                        if seconds or not ordered:
                            ordered.append(f"{seconds}s")
                        age_str = "".join(ordered[:2])
                        aage_tag = f" [{age_str}]"
                    except Exception:
                        aage_tag = ""
                abits = f"{asvc_name}: {atitle_stripped}" if asvc_name else atitle_stripped
                abits = abits.strip()
                if not abits:
                    continue
                atext = f"• {abits} {ast_tag}{aage_tag}".strip()
                awrapped = tw.wrap(re.sub(r"\[[^\]]+\]", lambda m: m.group(0).replace(" ", "\x07"), atext)) or [""]
                awrapped = [w.replace("\x07", " ") for w in awrapped]
                rows.append(["", awrapped[0]])
                for cont in awrapped[1:]:
                    rows.append(["", cont])

    return tabulate(rows, tablefmt="plain", colalign=("left", "left"))
