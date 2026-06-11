"""HomeScreen — the main incident list."""

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from jpd.monitor import actions as A
from jpd.monitor._log import get_logger
from jpd.monitor.incidents import IncidentsTable
from jpd.monitor.modals import FilterPickModal, HelpModal, InputModal
from jpd.query import _parse_snooze


log = get_logger("home")


class HomeScreen(Screen):
    """Incident list. Drill into an incident with right/Enter/l."""

    BINDINGS = [
        # Navigation
        Binding("right", "drill_in", "Drill in", show=False),
        Binding("l", "drill_in", "Drill in", show=False),
        # left/h are no-ops on Home (already home).
        # Marking + actions
        Binding("space", "mark", "Mark", show=True),
        Binding("a", "ack", "Ack"),
        Binding("R", "resolve", "Resolve"),
        Binding("s", "snooze_custom", "Snooze…"),
        Binding("S", "snooze_eos", "Snooze→EOS"),
        Binding("m", "merge", "Merge"),
        Binding("e", "edit_title", "Edit title"),
        Binding("f", "filter_menu", "Filter…"),
        Binding("W", "write_config", "Save"),
        Binding("question_mark", "help", "Help", show=False),
        # Esc opens the command palette (hamburger icon). Modals override
        # via their own bindings/on_key so Esc still dismisses dialogs.
        Binding("escape", "app.command_palette", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.table = IncidentsTable(id="home-table")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="☰")
        yield self.table
        yield Footer()

    def on_mount(self):
        app = self.app
        self.table.show_service_info = bool(app.mon_cfg.get("show_service_info", default=False))
        log.info("HomeScreen mounted; service_info=%s", self.table.show_service_info)
        self._update_subtitle()
        self._refresh_from_app()
        app.data_changed.subscribe(self, lambda _payload: self._refresh_from_app())
        log.debug("HomeScreen subscribed to data_changed")

    def on_unmount(self):
        # Textual cleans Signal subscriptions on unsubscribe; for transient
        # screens this matters less because the screen is gone.
        pass

    def on_screen_resume(self):
        self._update_subtitle()
        self._refresh_from_app()

    def _update_subtitle(self):
        self.app.sub_title = f"filter: {self.app.filt.description()}"

    def _refresh_from_app(self):
        log.debug("HomeScreen refresh: %d incidents", len(self.app.incidents))
        self.table.refresh_from(self.app.incidents)

    # ---- navigation ------------------------------------------------------

    def action_drill_in(self):
        row = self.table.current_row()
        if row is None:
            log.debug("drill_in: no cursor row")
            return
        inc = next((i for i in self.app.incidents if i.get("id") == row.iid), None)
        if inc is None:
            log.warning("drill_in: incident %s no longer in app.incidents", row.iid)
            self.app.notify("incident no longer present", severity="warning")
            return
        log.info("drill_in -> IncidentScreen iid=%s", row.iid)
        from jpd.monitor.incident import IncidentScreen
        self.app.push_screen(IncidentScreen(inc.get("id")))

    def on_data_table_row_selected(self, _event):
        self.action_drill_in()

    # ---- marking ---------------------------------------------------------

    def action_mark(self):
        self.table.toggle_mark()
        log.debug("mark toggled; marked set=%s", sorted(self.table.marked))
        self.table.refresh_from(self.app.incidents)

    # ---- incident-level actions ------------------------------------------

    def _selected_iids(self):
        marked = self.table.marked_incident_ids()
        if marked:
            return marked
        row = self.table.current_row()
        return [row.iid] if row is not None else []

    def action_ack(self):
        self._do_ack()

    @work
    async def _do_ack(self):
        ids = self._selected_iids()
        log.info("home.ack ids=%s", ids)
        if not ids:
            return
        for iid in ids:
            try:
                await A.ack(iid)
            except Exception as e:
                log.exception("home.ack %s failed: %s", iid, e)
                self.app.notify(f"ack {iid}: {e}", severity="error")
        self.table.marked.clear()
        await self.app._do_poll()

    def action_resolve(self):
        self._do_resolve()

    @work
    async def _do_resolve(self):
        ids = self._selected_iids()
        log.info("home.resolve ids=%s", ids)
        if not ids:
            return
        for iid in ids:
            try:
                await A.resolve(iid)
            except Exception as e:
                log.exception("home.resolve %s failed: %s", iid, e)
                self.app.notify(f"resolve {iid}: {e}", severity="error")
        self.table.marked.clear()
        await self.app._do_poll()

    def action_snooze_eos(self):
        self._do_snooze_eos()

    @work
    async def _do_snooze_eos(self):
        await self.app._refresh_eos()
        if not self.app.eos_secs:
            log.warning("home.snooze_eos: EOS unknown")
            self.app.notify("EOS unknown; press S for custom snooze", severity="warning")
            return
        ids = self._selected_iids()
        log.info("home.snooze_eos ids=%s for %ds", ids, self.app.eos_secs)
        for iid in ids:
            try:
                await A.snooze(iid, self.app.eos_secs)
            except Exception as e:
                log.exception("home.snooze_eos %s failed: %s", iid, e)
                self.app.notify(f"snooze {iid}: {e}", severity="error")
        self.table.marked.clear()
        await self.app._do_poll()

    def action_snooze_custom(self):
        self._do_snooze_custom()

    @work
    async def _do_snooze_custom(self):
        spec = await self.app.push_screen_wait(InputModal("Snooze for: (e.g. 1h, 90m, 19:00)"))
        if not spec:
            log.debug("home.snooze_custom: cancelled")
            return
        secs = _parse_snooze(spec)
        ids = self._selected_iids()
        log.info("home.snooze_custom spec=%r -> %ds ids=%s", spec, secs, ids)
        for iid in ids:
            try:
                await A.snooze(iid, secs)
            except Exception as e:
                log.exception("home.snooze_custom %s failed: %s", iid, e)
                self.app.notify(f"snooze {iid}: {e}", severity="error")
        self.table.marked.clear()
        await self.app._do_poll()

    def action_merge(self):
        self._do_merge()

    @work
    async def _do_merge(self):
        row = self.table.current_row()
        if row is None:
            return
        sources = [iid for iid in self.table.marked_incident_ids() if iid != row.iid]
        if not sources:
            log.debug("home.merge: no sources marked")
            self.app.notify("merge: mark sources with space first", severity="warning")
            return
        log.info("home.merge target=%s sources=%s; awaiting confirm", row.iid, sources)
        confirm = await self.app.push_screen_wait(InputModal(
            f"Merge {len(sources)} → {row.iid}? type 'yes' to confirm",
        ))
        if not confirm or confirm.strip().lower() != "yes":
            log.info("home.merge: cancelled (confirm=%r)", confirm)
            return
        try:
            await A.merge(row.iid, sources)
            log.info("home.merge: success")
        except Exception as e:
            log.exception("home.merge failed: %s", e)
            self.app.notify(f"merge: {e}", severity="error")
        self.table.marked.clear()
        await self.app._do_poll()

    def action_edit_title(self):
        self._do_edit_title()

    @work
    async def _do_edit_title(self):
        row = self.table.current_row()
        if row is None:
            return
        new_title = await self.app.push_screen_wait(InputModal("New title:", initial=row.title))
        if not new_title:
            return
        try:
            await A.edit_title(row.iid, new_title)
        except Exception as e:
            self.app.notify(f"edit-title: {e}", severity="error")
        await self.app._do_poll()

    # ---- filter ----------------------------------------------------------

    def action_filter_menu(self):
        self._do_filter_menu()

    @work
    async def _do_filter_menu(self):
        filt = self.app.filt
        scope = await self.app.push_screen_wait(FilterPickModal(filt))
        if scope is None:
            log.debug("filter_menu: cancelled")
            return
        log.info("filter_menu: picked scope=%s", scope)
        if scope == "custom":
            await self._edit_custom_filter()
            return
        prev = filt.scope
        filt.scope = scope
        try:
            filt._validate()
        except ValueError as e:
            log.warning("filter scope %s rejected: %s", scope, e)
            filt.scope = prev
            self.app.notify(str(e), severity="error")
            return
        self._update_subtitle()
        await self.app._do_poll()

    async def _edit_custom_filter(self):
        filt = self.app.filt
        cur_u = ",".join(filt.user_ids) or ""
        users = await self.app.push_screen_wait(
            InputModal("Custom user_ids (comma list, blank = none):", initial=cur_u)
        )
        if users is None:
            return
        cur_t = ",".join(filt.team_ids) or ""
        teams = await self.app.push_screen_wait(
            InputModal("Custom team_ids (comma list, blank = none):", initial=cur_t)
        )
        if teams is None:
            return
        prev_scope = filt.scope
        prev_users = list(filt.user_ids)
        prev_teams = list(filt.team_ids)
        filt.scope = "custom"
        filt.user_ids = [x.strip() for x in users.split(",") if x.strip()]
        filt.team_ids = [x.strip() for x in teams.split(",") if x.strip()]
        try:
            filt._validate()
        except ValueError as e:
            filt.scope = prev_scope
            filt.user_ids = prev_users
            filt.team_ids = prev_teams
            self.app.notify(str(e), severity="error")
            return
        self._update_subtitle()
        await self.app._do_poll()

    def action_write_config(self):
        app = self.app
        app.mon_cfg.set("auto_ack", app.auto_ack)
        app.filt.persist_into(app.mon_cfg)
        app.mon_cfg.write()
        log.info("wrote config to %s (auto_ack=%s filter=%s)",
                 app.mon_cfg.write_path, app.auto_ack, app.filt.description())
        app.notify(f"wrote {app.mon_cfg.write_path}")

    # ---- help ------------------------------------------------------------

    def action_help(self):
        state = self.app.help_state_lines()
        self.app.push_screen(HelpModal(
            screen_name="Home",
            screen_bindings=self.BINDINGS,
            app_bindings=self.app.BINDINGS,
            state_lines=state,
        ))
