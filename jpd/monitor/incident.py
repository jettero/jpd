"""IncidentScreen — drill into one incident; lists its alerts."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from jpd.monitor import actions as A
from jpd.monitor._log import get_logger
from jpd.monitor.alerts import AlertsTable
from jpd.monitor.modals import HelpModal, InputModal, PickIncidentModal
from jpd.query import _parse_snooze


log = get_logger("incident")


class IncidentScreen(Screen):
    """One incident + its alerts. Drill into an alert with right/Enter/l."""

    BINDINGS = [
        # Navigation — Esc no longer means back (it opens the command
        # palette). Use ← or h to back out. The first row in the alerts
        # table is a synthetic "[notes]" row that drills into InfoScreen.
        Binding("right", "drill_in", "Drill in", show=False),
        Binding("l", "drill_in", "Drill in", show=False),
        Binding("left", "back", "Back"),
        Binding("h", "back", "Back", show=False),
        # Actions
        Binding("a", "ack", "Ack"),
        Binding("R", "resolve", "Resolve"),
        Binding("s", "snooze_custom", "Snooze…"),
        Binding("S", "snooze_eos", "Snooze→EOS"),
        Binding("e", "edit_title", "Edit title"),
        Binding("M", "move_alert", "Move alert"),
        Binding("o", "cycle_sort", "Sort"),
        Binding("question_mark", "help", "Help", show=False),
        Binding("escape", "app.command_palette", show=False),
    ]

    def __init__(self, iid):
        super().__init__()
        self.iid = iid
        self.table = AlertsTable(id="incident-alerts")
        self.sort_mode = "newest"
        self._subscribed = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="☰")
        yield self.table
        yield Footer()

    def _incident(self):
        for inc in self.app.incidents or ():
            if inc.get("id") == self.iid:
                return inc
        return None

    def on_mount(self):
        self.table.show_service_info = bool(self.app.mon_cfg.get("show_service_info", default=False))
        log.info("IncidentScreen mounted iid=%s", self.iid)
        self._update_subtitle()
        self._refresh_from_app()
        self.app.data_changed.subscribe(self, lambda _payload: self._refresh_from_app())
        self._subscribed = True

    def on_screen_resume(self):
        self._update_subtitle()
        self._refresh_from_app()

    def _update_subtitle(self):
        inc = self._incident()
        title = (inc.get("title") or inc.get("summary") or "").strip() if inc else ""
        self.app.sub_title = f"› {self.iid} — {title}"

    def _refresh_from_app(self):
        inc = self._incident()
        if inc is None:
            log.warning("IncidentScreen refresh: iid=%s gone, popping", self.iid)
            self.app.notify(f"incident {self.iid} no longer present", severity="warning")
            try:
                self.app.pop_screen()
            except Exception as e:
                log.exception("pop_screen failed: %s", e)
            return
        n_alerts = len(inc.get("alerts") or ())
        log.debug("IncidentScreen refresh iid=%s alerts=%d sort=%s",
                  self.iid, n_alerts, self.sort_mode)
        self.table.refresh_from(inc, sort_mode=self.sort_mode)


    # ---- navigation ------------------------------------------------------

    def action_drill_in(self):
        row = self.table.current_row()
        if row is None:
            log.debug("incident.drill_in: no cursor")
            return
        if row.kind == "notes":
            from jpd.monitor.info import InfoScreen
            log.info("incident.drill_in -> InfoScreen iid=%s", self.iid)
            self.app.push_screen(InfoScreen(self.iid))
            return
        log.info("incident.drill_in -> AlertScreen iid=%s aid=%s", self.iid, row.aid)
        from jpd.monitor.alert import AlertScreen
        self.app.push_screen(AlertScreen(self.iid, row.aid))

    def on_data_table_row_selected(self, _event):
        self.action_drill_in()

    def action_back(self):
        log.info("incident.back from iid=%s", self.iid)
        self.app.pop_screen()

    def action_cycle_sort(self):
        from jpd.monitor.alerts import SORT_MODES
        i = SORT_MODES.index(self.sort_mode) if self.sort_mode in SORT_MODES else 0
        self.sort_mode = SORT_MODES[(i + 1) % len(SORT_MODES)]
        log.info("incident.sort -> %s", self.sort_mode)
        self.app.notify(f"sort: {self.sort_mode}", timeout=2)
        self._refresh_from_app()

    # ---- incident actions ------------------------------------------------

    def action_ack(self):
        self._do_ack()

    @work
    async def _do_ack(self):
        try:
            await A.ack(self.iid)
        except Exception as e:
            self.app.notify(f"ack: {e}", severity="error")
        await self.app._do_poll()

    def action_resolve(self):
        self._do_resolve()

    @work
    async def _do_resolve(self):
        try:
            await A.resolve(self.iid)
            self.app.notify(f"resolved {self.iid}")
        except Exception as e:
            log.exception("incident.resolve %s failed: %s", self.iid, e)
            self.app.notify(f"resolve: {e}", severity="error")
        await self.app._do_poll()

    def action_snooze_eos(self):
        self._do_snooze_eos()

    @work
    async def _do_snooze_eos(self):
        await self.app._refresh_eos()
        if not self.app.eos_secs:
            self.app.notify("EOS unknown; press S for custom snooze", severity="warning")
            return
        try:
            await A.snooze(self.iid, self.app.eos_secs)
        except Exception as e:
            self.app.notify(f"snooze: {e}", severity="error")
        await self.app._do_poll()

    def action_snooze_custom(self):
        self._do_snooze_custom()

    @work
    async def _do_snooze_custom(self):
        spec = await self.app.push_screen_wait(InputModal("Snooze for: (e.g. 1h, 90m, 19:00)"))
        if not spec:
            return
        secs = _parse_snooze(spec)
        try:
            await A.snooze(self.iid, secs)
        except Exception as e:
            self.app.notify(f"snooze: {e}", severity="error")
        await self.app._do_poll()

    def action_edit_title(self):
        self._do_edit_title()

    @work
    async def _do_edit_title(self):
        inc = self._incident()
        if inc is None:
            return
        cur = inc.get("title") or inc.get("summary") or ""
        new_title = await self.app.push_screen_wait(InputModal("New title:", initial=cur))
        if not new_title:
            return
        try:
            await A.edit_title(self.iid, new_title)
        except Exception as e:
            self.app.notify(f"edit-title: {e}", severity="error")
        await self.app._do_poll()

    # ---- alert-level (move) ----------------------------------------------

    def action_move_alert(self):
        self._do_move_alert()

    @work
    async def _do_move_alert(self):
        row = self.table.current_row()
        if row is None:
            return
        dest = await self.app.push_screen_wait(
            PickIncidentModal(self.app.incidents, exclude_iid=self.iid)
        )
        if not dest:
            return
        if dest == "__NEW__":
            title = await self.app.push_screen_wait(InputModal("New incident title:"))
            if not title:
                return
            svc_id = row.service_id or ((self._incident() or {}).get("service") or {}).get("id")
            new_inc = await A.create_incident(title, svc_id)
            dest = new_inc.get("id") if isinstance(new_inc, dict) else None
            if not dest:
                self.app.notify("failed to create new incident", severity="error")
                return
        try:
            await A.move_alert(row.aid, dest, self.iid)
        except Exception as e:
            self.app.notify(f"move-alert: {e}", severity="error")
            return
        self.app.notify(f"moved {row.aid} → {dest}")
        await self.app._do_poll()

    # ---- help ------------------------------------------------------------

    def action_help(self):
        self.app.push_screen(HelpModal(
            screen_name=f"Incident {self.iid}",
            screen_bindings=self.BINDINGS,
            app_bindings=self.app.BINDINGS,
            state_lines=self.app.help_state_lines(),
        ))
