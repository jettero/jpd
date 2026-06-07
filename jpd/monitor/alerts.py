"""AlertsTable — one selectable container per alert, used inside IncidentScreen.

Mirrors the pattern in jpd/monitor/incidents.py exactly:
  - DataTable with cell_padding=0, show_header=False
  - One row per alert, multi-line via textwrap, height=N so the cursor
    highlights the whole alert container
  - Cursor parking via ↓-unparks / ↑-at-row-0-parks (starts parked)
"""

import shutil
import textwrap

from rich.text import Text
from textual.widgets import DataTable

from jpd.monitor._log import get_logger
from jpd.render import build_incident_rows, colorize_one


log = get_logger("widget.alerts")


# Same column layout as IncidentsTable so the visual feel matches.
ID_COL = 14
GAP_AFTER_ID = 2
SYM_COL = 1
GAP_AFTER_SYM = 2
LEADER_WIDTH = ID_COL + GAP_AFTER_ID + SYM_COL + GAP_AFTER_SYM  # 19


def _total_width():
    return max(40, shutil.get_terminal_size((80, 24)).columns)


def _wrap_width():
    return _total_width() - LEADER_WIDTH


class AlertRow:
    """Meta for one selectable row.

    kind="alert" — a real alert (aid/title/service/status populated).
    kind="notes" — synthetic row at the top that drills into the incident
                   info screen (summary + notes). Other fields are None.
    """

    __slots__ = ("kind", "aid", "title", "service_id", "status")

    def __init__(self, kind, aid, title, service_id, status):
        self.kind = kind
        self.aid = aid
        self.title = title
        self.service_id = service_id
        self.status = status


class AlertsTable(DataTable):
    BINDINGS = []

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.cursor_type = "row"
        self.zebra_stripes = False
        self.show_header = False
        self.cell_padding = 0
        # On the IncidentScreen the user just chose this incident; show the
        # cursor on the first alert so the next move/expand keystroke has
        # a target. Manual park-via-↑-at-row-0 still works.
        self.show_cursor = True
        self.rows_meta = []
        self._cols_added = False
        self.show_service_info = False

    def on_mount(self):
        if not self._cols_added:
            self.add_column("Alert", width=_total_width())
            self._cols_added = True

    def refresh_from(self, incident, sort_mode="newest"):
        """incident is a single incident dict; we render its alerts only.

        sort_mode: "newest" (default — most recent created_at first),
                   "oldest", or "status" (triggered first, then ack).
        """
        log.debug("AlertsTable refresh_from: incident=%s alerts=%d sort=%s",
                  incident.get("id") if incident else None,
                  len(incident.get("alerts") or ()) if incident else 0,
                  sort_mode)
        self.clear()
        self.rows_meta = []
        if not incident:
            return

        # Synthetic first row — drills into the InfoScreen (summary + notes).
        # Always present so the existence of an info view is discoverable.
        info_leader = f"{' ' * ID_COL}{' ' * GAP_AFTER_ID}i{' ' * GAP_AFTER_SYM}"
        info_text = Text(info_leader)
        info_text.append("[notes]", style="bold magenta")
        info_text.append("   ", style="")
        info_text.append("incident summary + notes", style="dim")
        self.add_row(info_text, height=1)
        self.rows_meta.append(AlertRow(
            kind="notes", aid=None, title="notes", service_id=None, status=None,
        ))

        sorted_incident = _with_sorted_alerts(incident, sort_mode)
        all_rows = build_incident_rows(
            [sorted_incident],
            show_service_info=self.show_service_info,
            show_alerts=True,
            expanded=None,
        )
        wrap_w = _wrap_width()
        alerts_by_id = {a.get("id"): a for a in incident.get("alerts") or ()}
        for _iid, symbol, text, meta in all_rows:
            if meta.get("kind") != "alert":
                continue
            wrapped = textwrap.wrap(
                text or " ",
                width=wrap_w,
                break_long_words=False,
                break_on_hyphens=False,
            ) or [""]
            leader = f"{' ' * ID_COL}{' ' * GAP_AFTER_ID}{symbol}{' ' * GAP_AFTER_SYM}"
            cont = " " * LEADER_WIDTH
            lines = [f"{leader}{wrapped[0]}"]
            for w in wrapped[1:]:
                lines.append(f"{cont}{w}")
            joined = "\n".join(lines)
            styled = Text.from_ansi(colorize_one(joined))
            self.add_row(styled, height=len(lines))
            alert = alerts_by_id.get(meta.get("aid")) or {}
            self.rows_meta.append(AlertRow(
                kind="alert",
                aid=meta.get("aid") or "",
                title=meta.get("title") or "",
                service_id=meta.get("service_id") or "",
                status=alert.get("status") or "",
            ))

    def current_row(self):
        idx = self.cursor_row
        if idx is None or idx < 0 or idx >= len(self.rows_meta):
            return None
        return self.rows_meta[idx]

    def action_cursor_down(self):
        if not self.show_cursor:
            log.debug("AlertsTable: unpark via ↓ at row=%s", self.cursor_row)
            self.show_cursor = True
            return
        super().action_cursor_down()

    def action_cursor_up(self):
        if not self.show_cursor:
            return
        if self.cursor_row <= 0:
            log.debug("AlertsTable: park via ↑ at row=0")
            self.show_cursor = False
            return
        super().action_cursor_up()

    def action_cursor_right(self):
        screen = self.screen
        if screen is not None and hasattr(screen, "action_drill_in"):
            screen.action_drill_in()

    def action_cursor_left(self):
        screen = self.screen
        if screen is not None and hasattr(screen, "action_back"):
            screen.action_back()


SORT_MODES = ("newest", "oldest", "status")

# triggered first, then acknowledged, then everything else
_STATUS_ORDER = {"triggered": 0, "acknowledged": 1, "resolved": 2}


def _with_sorted_alerts(incident, mode):
    """Return a shallow copy of the incident with its alerts reordered.

    We copy because the dict comes from the App's polled list — sorting
    in place would mutate shared state.
    """
    alerts = list(incident.get("alerts") or ())
    if not alerts:
        return incident
    if mode == "oldest":
        alerts.sort(key=lambda a: a.get("created_at") or "")
    elif mode == "status":
        alerts.sort(key=lambda a: (
            _STATUS_ORDER.get(a.get("status", ""), 99),
            # tiebreak with newest-first so within a status group recent wins
            -_iso_to_sortable(a.get("created_at")),
        ))
    else:  # newest (default)
        alerts.sort(key=lambda a: a.get("created_at") or "", reverse=True)
    new_inc = dict(incident)
    new_inc["alerts"] = alerts
    return new_inc


def _iso_to_sortable(iso):
    """Cheap iso-string → comparable float for tiebreak only; bad/missing
    strings sort as 0 so they tie."""
    if not iso:
        return 0.0
    try:
        from datetime import datetime
        s = iso.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0
