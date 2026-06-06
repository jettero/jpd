"""Incidents table — one selectable container per incident.

Each DataTable row is ONE incident container holding all of its own lines:
the incident header plus every alert plus every wrap-continuation line. The
cursor navigates incident-to-incident, never line-by-line; the entire
container is highlighted at once.

Per-alert actions (move-alert) reach the alert via a modal sub-picker
launched from the container's incident, since this widget no longer
distinguishes alerts at the row level.
"""

import shutil
import textwrap

from rich.text import Text
from textual.widgets import DataTable

from jpd.monitor._log import get_logger
from jpd.render import build_incident_rows, colorize_one


log = get_logger("widget.incidents")


# Match render.py's layout: ID(14) + 2sp gap + symbol(1) + 2sp gap + content.
ID_COL = 14
GAP_AFTER_ID = 2
SYM_COL = 1
GAP_AFTER_SYM = 2
LEADER_WIDTH = ID_COL + GAP_AFTER_ID + SYM_COL + GAP_AFTER_SYM  # 19


def _total_width():
    return max(40, shutil.get_terminal_size((80, 24)).columns)


def _wrap_width():
    return _total_width() - LEADER_WIDTH


class Row:
    """Meta for one selectable incident container."""

    __slots__ = ("iid", "title", "service_id", "alerts")

    def __init__(self, iid, title, service_id, alerts):
        self.iid = iid
        self.title = title
        self.service_id = service_id
        # alerts: [(alert_id, alert_title, service_id), ...]
        self.alerts = alerts


def _format_leader(iid_str, symbol):
    return f"{iid_str:<{ID_COL}}{' ' * GAP_AFTER_ID}{symbol}{' ' * GAP_AFTER_SYM}"


def _alert_leader(symbol):
    return f"{' ' * ID_COL}{' ' * GAP_AFTER_ID}{symbol}{' ' * GAP_AFTER_SYM}"


def _cont_leader():
    return " " * LEADER_WIDTH


class IncidentsTable(DataTable):
    BINDINGS = []

    def __init__(self, *a, **kw):
        kw.pop("columns", None)
        super().__init__(*a, **kw)
        self.cursor_type = "row"
        self.zebra_stripes = False
        self.show_header = False
        # No internal column padding so wrap width and visual width match.
        self.cell_padding = 0
        # Start parked — user surfaces the cursor with ↓.
        self.show_cursor = False
        self.rows_meta = []
        self.marked = set()
        self.show_service_info = False
        self._cols_added = False

    def on_mount(self):
        if not self._cols_added:
            self.add_column("Incident", width=_total_width())
            self._cols_added = True

    def refresh_from(self, incidents):
        log.debug("IncidentsTable refresh_from: %d incidents wrap_w=%d",
                  len(incidents or ()), _wrap_width())
        self.clear()
        self.rows_meta = []
        wrap_w = _wrap_width()
        for inc in incidents or ():
            rows = build_incident_rows(
                [inc],
                show_service_info=self.show_service_info,
                show_alerts=True,
                expanded=None,
            )
            lines = []
            alerts_meta = []
            for iid_str, symbol, text, meta in rows:
                wrapped = textwrap.wrap(
                    text or " ",
                    width=wrap_w,
                    break_long_words=False,
                    break_on_hyphens=False,
                ) or [""]
                if meta["kind"] == "incident":
                    leader = _format_leader(iid_str, symbol)
                else:
                    leader = _alert_leader(symbol)
                    alerts_meta.append((meta["aid"], meta["title"], meta["service_id"]))
                lines.append(f"{leader}{wrapped[0]}")
                cont = _cont_leader()
                for w in wrapped[1:]:
                    lines.append(f"{cont}{w}")

            joined = "\n".join(lines) if lines else " "
            styled = Text.from_ansi(colorize_one(joined))
            iid = inc.get("id") or ""
            if iid in self.marked:
                styled.stylize("reverse")
            self.add_row(styled, height=max(1, len(lines)))
            self.rows_meta.append(Row(
                iid=iid,
                title=inc.get("title") or inc.get("summary") or "",
                service_id=(inc.get("service") or {}).get("id") or "",
                alerts=alerts_meta,
            ))

    def current_row(self):
        idx = self.cursor_row
        if idx is None or idx < 0 or idx >= len(self.rows_meta):
            return None
        return self.rows_meta[idx]

    def toggle_mark(self):
        row = self.current_row()
        if row is None:
            return
        if row.iid in self.marked:
            self.marked.discard(row.iid)
        else:
            self.marked.add(row.iid)

    def marked_incident_ids(self):
        return list(self.marked)

    def toggle_cursor_visible(self):
        self.show_cursor = not self.show_cursor

    def action_cursor_down(self):
        # Parked → first ↓ surfaces the cursor at the current row, no advance.
        if not self.show_cursor:
            log.debug("IncidentsTable: unpark via ↓ at row=%s", self.cursor_row)
            self.show_cursor = True
            return
        super().action_cursor_down()

    def action_cursor_up(self):
        # Already parked: ignore.
        if not self.show_cursor:
            return
        # At the top: ↑ re-parks (matches the user's "above-the-list" intent).
        if self.cursor_row <= 0:
            log.debug("IncidentsTable: park via ↑ at row=0")
            self.show_cursor = False
            return
        super().action_cursor_up()

    # Repurpose horizontal-cursor keys for tree navigation. In row-cursor
    # mode they're otherwise meaningless, and we want them to drive screen
    # left/right (back / drill in).
    def action_cursor_right(self):
        screen = self.screen
        if screen is not None and hasattr(screen, "action_drill_in"):
            screen.action_drill_in()

    def action_cursor_left(self):
        screen = self.screen
        if screen is not None and hasattr(screen, "action_back"):
            screen.action_back()
