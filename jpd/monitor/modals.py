"""Small reusable modals used across the monitor screens.

Kept thin — these are transient dialogs (input, pick-from-list,
read-only-detail, help overlay). Full-screen content lives in the
HomeScreen / IncidentScreen / AlertScreen classes, not here.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView, Static

from jpd.monitor._log import get_logger


log = get_logger("modals")


class InputModal(ModalScreen):
    """Single-line input. Returns the typed string, or None on Esc."""

    def __init__(self, prompt, initial=""):
        super().__init__()
        self.prompt = prompt
        self.initial = initial

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.prompt, markup=False),
            Input(value=self.initial, id="modal-input"),
            id="modal-box",
        )

    def on_input_submitted(self, event):
        log.info("InputModal submitted: prompt=%r value=%r", self.prompt, event.value)
        self.dismiss(event.value)

    def on_key(self, event):
        if event.key == "escape":
            log.info("InputModal cancelled: prompt=%r", self.prompt)
            self.dismiss(None)


class StaticDetailModal(ModalScreen):
    """Read-only scrollable detail view."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("enter", "close", "Close"),
    ]

    def __init__(self, title, body):
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self._title, id="detail-title", markup=False),
            VerticalScroll(Static(self._body, id="detail-body", markup=False), id="detail-scroll"),
            Label("[ Esc / q / Enter to close ]", id="detail-hint"),
            id="modal-box",
        )

    def action_close(self):
        self.dismiss(None)


class PickIncidentModal(ModalScreen):
    """Pick one incident from a list (used when moving an alert).

    Returns the chosen incident id, "__NEW__" to create a new one, or None
    on Esc.
    """

    def __init__(self, incidents, exclude_iid=None):
        super().__init__()
        self.incidents = [i for i in (incidents or ()) if i.get("id") != exclude_iid]

    def compose(self) -> ComposeResult:
        items = []
        for inc in self.incidents:
            label = f"{inc.get('id')}  [{inc.get('status', '?')}]  {inc.get('title') or inc.get('summary') or ''}"
            li = ListItem(Label(label, markup=False))
            li.iid = inc.get("id")
            items.append(li)
        yield Vertical(
            Label("Move alert into which incident? (Enter=pick, n=new, Esc=cancel)"),
            ListView(*items, id="pick-list"),
            id="modal-box",
        )

    def on_list_view_selected(self, event):
        log.info("PickIncidentModal selected: iid=%s", event.item.iid)
        self.dismiss(event.item.iid)

    def on_key(self, event):
        if event.key == "escape":
            log.info("PickIncidentModal cancelled")
            self.dismiss(None)
        elif event.key == "n":
            log.info("PickIncidentModal: __NEW__")
            self.dismiss("__NEW__")


class FilterPickModal(ModalScreen):
    """Pick a filter scope: mine / team / custom. Returns the chosen
    scope name, or None on Esc. Selecting `custom` is the entry point
    to the custom user_ids / team_ids editor — the caller chains the
    edit flow when it sees `custom` come back.

    The row labels show the live underlying values (JPDC.user_id,
    JPDC.team_ids, the current FilterModel's custom lists) so users
    can see what each scope means without having to commit.
    """

    SCOPES = ("mine", "team", "custom")

    def __init__(self, filt):
        super().__init__()
        from jpd.config import JPDC
        self._filt = filt
        u = JPDC.user_id or "(no user_id)"
        team_ids = list(JPDC.team_ids) or []
        team_part = ", ".join(team_ids) if team_ids else "(no teams configured)"
        cust_bits = []
        if filt.user_ids:
            cust_bits.append("u=" + ",".join(filt.user_ids))
        if filt.team_ids:
            cust_bits.append("t=" + ",".join(filt.team_ids))
        cust_part = " ".join(cust_bits) if cust_bits else "(edit…)"
        self._row_labels = {
            "mine":   f"mine — {u}",
            "team":   f"team — {team_part}",
            "custom": f"custom — {cust_part}",
        }

    def compose(self) -> ComposeResult:
        items = []
        for scope in self.SCOPES:
            li = ListItem(Label(self._row_labels[scope], markup=False))
            li.scope = scope
            items.append(li)
        yield Vertical(
            Label("Filter — pick a scope"),
            ListView(*items, id="pick-list"),
            id="modal-box",
        )

    def on_mount(self):
        lv = self.query_one("#pick-list", ListView)
        try:
            lv.index = self.SCOPES.index(self._filt.scope)
        except ValueError:
            lv.index = 0

    def on_list_view_selected(self, event):
        log.info("FilterPickModal selected: scope=%s", event.item.scope)
        self.dismiss(event.item.scope)

    def on_key(self, event):
        if event.key == "escape":
            log.info("FilterPickModal cancelled")
            self.dismiss(None)


class HelpModal(ModalScreen):
    """Show the current screen's BINDINGS plus app-level global state.

    Built dynamically from the screen passed in at construction time, so
    each screen gets its own help.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("question_mark", "close", "Close"),
    ]

    def __init__(self, screen_name, screen_bindings, app_bindings, state_lines):
        super().__init__()
        self._screen_name = screen_name
        self._screen_bindings = screen_bindings
        self._app_bindings = app_bindings
        self._state_lines = state_lines

    def _fmt_bindings(self, bindings):
        lines = []
        for b in bindings:
            if not b.show:
                continue
            lines.append(f"  {b.key:<14} {b.description}")
        return "\n".join(lines) or "  (none)"

    def compose(self) -> ComposeResult:
        body = []
        body.append(f"Screen: {self._screen_name}")
        body.append("")
        body.append("Keys (this screen):")
        body.append(self._fmt_bindings(self._screen_bindings))
        body.append("")
        body.append("Keys (global):")
        body.append(self._fmt_bindings(self._app_bindings))
        body.append("")
        body.append("State:")
        for line in self._state_lines:
            body.append(f"  {line}")
        yield Vertical(
            Label("Help", id="detail-title"),
            VerticalScroll(Static("\n".join(body), id="detail-body", markup=False), id="detail-scroll"),
            Label("[ Esc / q / ? to close ]", id="detail-hint"),
            id="modal-box",
        )

    def action_close(self):
        self.dismiss(None)
