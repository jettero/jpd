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


class AutoExitModal(ModalScreen):
    """Manage scheduled + one-off auto-exit conditions.

    First-cut UI: a list of armed conditions (soonest first) with live
    countdowns, plus action rows to add a one-off timer, add a persisted
    schedule entry, or clear everything. `d`/`delete` removes the highlighted
    condition. All mutation goes through the app's exit-condition API, which
    re-arms the timers and persists the schedule.
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close"),
        Binding("d", "remove", "Remove"),
        Binding("delete", "remove", "Remove"),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Auto-exit conditions", id="detail-title"),
            ListView(id="auto-exit-list"),
            Label("Enter=activate · d=remove · Esc=close", id="detail-hint"),
            id="modal-box",
        )

    async def on_mount(self):
        await self._rebuild()

    async def _rebuild(self):
        from jpd.monitor.app import _pretty_secs

        lv = self.query_one("#auto-exit-list", ListView)
        await lv.clear()
        items = []
        for kind, spec, secs in self.app.exit_conditions():
            label = f"{spec:<12} [{kind}]   in {_pretty_secs(secs)}"
            li = ListItem(Label(label, markup=False))
            li.meta = ("cond", kind, spec)
            items.append(li)
        for key, text in (
            ("add_oneoff", "＋ Add one-off timer…"),
            ("add_sched", "＋ Add to schedule (persists)…"),
            ("clear", "✗ Clear all"),
        ):
            li = ListItem(Label(text, markup=False))
            li.meta = ("action", key, None)
            items.append(li)
        await lv.extend(items)
        # extend() leaves index None → nothing highlighted → Enter/`d` are
        # no-ops. Highlight the first row so the list is immediately usable.
        if len(lv):
            lv.index = 0

    async def on_list_view_selected(self, event):
        meta = getattr(event.item, "meta", None)
        if not meta:
            return
        typ, key, _ = meta
        if typ != "action":
            return  # condition rows: use `d` to remove
        if key == "add_oneoff":
            self._add(persist=False)
        elif key == "add_sched":
            self._add(persist=True)
        elif key == "clear":
            log.info("AutoExitModal: clear all")
            self.app.clear_exit_conditions()
            await self._rebuild()

    def _add(self, persist):
        prompt = ("Save to schedule — 9pm / 21:00 / 7h30m / 90m:" if persist
                  else "One-off exit — 9pm / 21:00 / 7h30m / 90m:")

        def _done(spec):
            if spec:
                log.info("AutoExitModal: add %s spec=%r",
                         "schedule" if persist else "one-off", spec)
                self.app.add_exit_condition(spec, persist=persist)
            self.run_worker(self._rebuild())

        self.app.push_screen(InputModal(prompt), _done)

    async def action_remove(self):
        lv = self.query_one("#auto-exit-list", ListView)
        item = lv.highlighted_child
        meta = getattr(item, "meta", None)
        if not meta or meta[0] != "cond":
            return
        _, kind, spec = meta
        log.info("AutoExitModal: remove %s spec=%r", kind, spec)
        self.app.remove_exit_condition(kind, spec)
        await self._rebuild()

    def action_close(self):
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
