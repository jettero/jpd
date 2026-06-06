"""InfoScreen — incident summary + notes, all in one scrollable column.

Reachable from IncidentScreen via `i`. Lives "to the side" rather than
deeper in the tree — left/h/Esc-via-palette all go back to IncidentScreen
(not to AlertScreen). Right is a no-op here.

We keep summary and notes in ONE Static inside ONE VerticalScroll so the
layout is robust against tiny terminals (the user reported 22-row tmux
panes wrecking stacked fixed-height widgets).
"""

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from jpd.monitor import actions as A
from jpd.monitor._log import get_logger
from jpd.monitor.alert_format import format_incident_summary, format_notes
from jpd.monitor.modals import HelpModal


log = get_logger("info")


class InfoScreen(Screen):
    """Summary + notes for one incident, single scrollable body."""

    BINDINGS = [
        Binding("left", "back", "Back"),
        Binding("h", "back", "Back", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("escape", "command_palette", show=False),
        # Right/l/Enter are no-ops here — nothing to drill into.
    ]

    def __init__(self, iid):
        super().__init__()
        self.iid = iid
        self._body_widget = None
        self._notes = []  # populated by _fetch_notes

    def _incident(self):
        for inc in self.app.incidents or ():
            if inc.get("id") == self.iid:
                return inc
        return None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="☰")
        self._body_widget = Static(self._render_body(), id="info-body", markup=False)
        yield VerticalScroll(self._body_widget, id="info-scroll")
        yield Footer()

    def on_mount(self):
        log.info("InfoScreen mounted iid=%s", self.iid)
        self._update_subtitle()
        self.app.data_changed.subscribe(self, lambda _payload: self._refresh())
        self._fetch_notes()

    def on_screen_resume(self):
        self._update_subtitle()
        self._refresh()
        self._fetch_notes()

    def _update_subtitle(self):
        inc = self._incident()
        title = (inc.get("title") or inc.get("summary") or "").strip() if inc else ""
        self.app.sub_title = f"› {self.iid} — {title}  (info)"

    def _refresh(self):
        if self._body_widget is not None:
            self._body_widget.update(self._render_body())

    def _render_body(self):
        out = Text()
        inc = self._incident()
        if inc is None:
            out.append("(incident no longer present)", style="dim italic")
            return out
        out.append_text(format_incident_summary(inc))
        out.append("\n")
        out.append("━━━ notes ", style="dim")
        out.append("━" * 50, style="dim")
        out.append("\n\n")
        out.append_text(format_notes(self._notes))
        return out

    @work(exclusive=True)
    async def _fetch_notes(self):
        try:
            notes = await A.fetch_notes(self.iid)
        except Exception as e:
            log.exception("fetch_notes failed for %s: %s", self.iid, e)
            self._notes = []
            self._refresh()
            return
        log.debug("InfoScreen %s: %d notes fetched", self.iid, len(notes or ()))
        self._notes = notes or []
        self._refresh()

    def action_back(self):
        log.info("info.back from iid=%s", self.iid)
        self.app.pop_screen()

    def action_help(self):
        self.app.push_screen(HelpModal(
            screen_name=f"Info {self.iid}",
            screen_bindings=self.BINDINGS,
            app_bindings=self.app.BINDINGS,
            state_lines=self.app.help_state_lines(),
        ))
