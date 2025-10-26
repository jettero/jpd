#!/usr/bin/env python
# coding: utf-8

import os
import textwrap
from typing import Iterable, List, Dict, Any
from tabulate import tabulate


def incidents_to_text(
    incidents: Iterable[Dict[str, Any]],
    *,
    show_team_info: bool = False,
    columns_env: str | None = None,
) -> str:
    """Render incidents as a two-column plain text table.

    - Left column: ID
    - Right column: wrapped summary with status/priority/assignee (and optional team)
    - Respects terminal width via COLUMNS env (defaults to 80)
    - Avoids breaking words inside square brackets
    """
    cols = int((columns_env or os.environ.get("COLUMNS") or 80))
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
        status_tag = f"[status: {st}]" if st else ""

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
                assignee = f" [assignee: {uname}]"

        # optional team
        team_part = ""
        if show_team_info:
            teams = inc.get("teams") or []
            tname = None
            if teams:
                t = teams[0] or {}
                tname = t.get("summary") or t.get("name") or t.get("id")
            if tname:
                team_part = f" [team: {tname}]"

        service = inc.get("service") or {}
        svc = service.get("summary") or service.get("name") or ""
        svc_part = f"{svc}: " if svc else ""

        summary = inc.get("title") or inc.get("summary") or ""
        text = f"{svc_part}{summary} {status_tag}{pr}{assignee}{team_part}".strip()

        wrapped = tw.wrap(text) or [""]
        rows.append([iid, wrapped[0]])
        for cont in wrapped[1:]:
            rows.append(["", cont])

    return tabulate(rows, tablefmt="plain", colalign=("left", "left"))
