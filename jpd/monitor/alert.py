"""AlertScreen — full-screen scrollable view of one alert's body."""

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from jpd.monitor import actions as A
from jpd.monitor._log import get_logger
from jpd.monitor.alert_format import format_alert
from jpd.monitor.modals import HelpModal, InputModal, PickIncidentModal


log = get_logger("alert")


class AlertScreen(Screen):
    """One alert's body, scrollable."""

    BINDINGS = [
        # Navigation — Esc no longer means back (it opens the command
        # palette). Use ← or h to back out.
        Binding("left", "back", "Back"),
        Binding("h", "back", "Back", show=False),
        # Right/l/Enter are no-ops on the alert screen — nothing deeper.
        # Actions
        Binding("a", "ack_parent", "Ack incident"),
        Binding("s", "snooze_custom_parent", "Snooze…"),
        Binding("S", "snooze_eos_parent", "Snooze→EOS"),
        Binding("M", "move_alert", "Move alert"),
        # Scrolling — VerticalScroll handles PgUp/PgDn/Home/End by default
        Binding("question_mark", "help", "Help", show=False),
        Binding("escape", "command_palette", show=False),
    ]

    def __init__(self, iid, aid):
        super().__init__()
        self.iid = iid
        self.aid = aid
        self._body_widget = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="☰")
        # Pass a Rich Text directly — Static renders Rich renderables
        # natively, so we get the per-token styling (URLs underlined,
        # status keywords colored, link/image shapes recognized) without
        # going through markup parsing (which choked on bracketed content).
        self._body_widget = Static(self._render_body(), id="alert-body", markup=False)
        yield VerticalScroll(self._body_widget, id="alert-scroll")
        yield Footer()

    def _incident(self):
        for inc in self.app.incidents or ():
            if inc.get("id") == self.iid:
                return inc
        return None

    def _alert(self):
        inc = self._incident()
        if inc is None:
            return None
        for a in inc.get("alerts") or ():
            if a.get("id") == self.aid:
                return a
        return None

    def on_mount(self):
        log.info("AlertScreen mounted iid=%s aid=%s", self.iid, self.aid)
        self._update_subtitle()
        self.app.data_changed.subscribe(self, lambda _payload: self._refresh_from_app())

    def on_screen_resume(self):
        self._update_subtitle()
        self._refresh_from_app()

    def _update_subtitle(self):
        alert = self._alert()
        title = (alert.get("summary") or alert.get("title") or "").strip() if alert else ""
        self.app.sub_title = f"› {self.iid} › {self.aid} — {title}"

    def _refresh_from_app(self):
        inc = self._incident()
        if inc is None:
            log.warning("AlertScreen refresh: incident %s gone, popping twice", self.iid)
            self.app.notify(f"incident {self.iid} gone", severity="warning")
            for _ in range(2):
                try:
                    self.app.pop_screen()
                except Exception as e:
                    log.exception("pop_screen failed: %s", e)
                    break
            return
        alert = self._alert()
        if alert is None:
            log.warning("AlertScreen refresh: alert %s gone, popping", self.aid)
            self.app.notify(f"alert {self.aid} gone", severity="warning")
            try:
                self.app.pop_screen()
            except Exception as e:
                log.exception("pop_screen failed: %s", e)
            return
        log.debug("AlertScreen refresh iid=%s aid=%s", self.iid, self.aid)
        if self._body_widget is not None:
            self._body_widget.update(self._render_body())

    def _render_body(self):
        alert = self._alert()
        if alert is None:
            return Text("(alert no longer present)", style="dim italic")
        return format_alert(alert)

    # ---- navigation ------------------------------------------------------

    def action_back(self):
        log.info("alert.back from iid=%s aid=%s", self.iid, self.aid)
        self.app.pop_screen()

    # ---- actions ---------------------------------------------------------

    def action_ack_parent(self):
        self._do_ack_parent()

    @work
    async def _do_ack_parent(self):
        try:
            await A.ack(self.iid)
        except Exception as e:
            self.app.notify(f"ack: {e}", severity="error")
        await self.app._do_poll()

    def action_snooze_eos_parent(self):
        self._do_snooze_eos_parent()

    @work
    async def _do_snooze_eos_parent(self):
        await self.app._refresh_eos()
        if not self.app.eos_secs:
            self.app.notify("EOS unknown", severity="warning")
            return
        try:
            await A.snooze(self.iid, self.app.eos_secs)
        except Exception as e:
            self.app.notify(f"snooze: {e}", severity="error")
        await self.app._do_poll()

    def action_snooze_custom_parent(self):
        self._do_snooze_custom_parent()

    @work
    async def _do_snooze_custom_parent(self):
        from jpd.query import _parse_snooze
        spec = await self.app.push_screen_wait(InputModal("Snooze for: (e.g. 1h, 90m, 19:00)"))
        if not spec:
            return
        secs = _parse_snooze(spec)
        try:
            await A.snooze(self.iid, secs)
        except Exception as e:
            self.app.notify(f"snooze: {e}", severity="error")
        await self.app._do_poll()

    def action_move_alert(self):
        self._do_move_alert()

    @work
    async def _do_move_alert(self):
        alert = self._alert()
        if alert is None:
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
            svc_id = (alert.get("service") or {}).get("id") or ((self._incident() or {}).get("service") or {}).get("id")
            new_inc = await A.create_incident(title, svc_id)
            dest = new_inc.get("id") if isinstance(new_inc, dict) else None
            if not dest:
                self.app.notify("failed to create new incident", severity="error")
                return
        try:
            await A.move_alert(self.aid, dest, self.iid)
        except Exception as e:
            self.app.notify(f"move-alert: {e}", severity="error")
            return
        self.app.notify(f"moved → {dest}")
        # The alert is now under another incident; pop back so user isn't
        # staring at a missing alert. Refresh signal will cascade as needed.
        try:
            self.app.pop_screen()
        except Exception:
            pass
        await self.app._do_poll()

    # ---- help ------------------------------------------------------------

    def action_help(self):
        self.app.push_screen(HelpModal(
            screen_name=f"Alert {self.aid}",
            screen_bindings=self.BINDINGS,
            app_bindings=self.app.BINDINGS,
            state_lines=self.app.help_state_lines(),
        ))


def _dump_alert(alert):
    """Plain-text dump — kept for the StaticDetailModal fallback in
    IncidentScreen (the legacy 'show alert raw' modal path)."""
    import json
    bits = []
    for k in ("id", "status", "created_at", "html_url"):
        v = alert.get(k)
        if v:
            bits.append(f"{k}: {v}")
    svc = alert.get("service") or {}
    if svc.get("summary"):
        bits.append(f"service: {svc.get('summary')}")
    bits.append("")
    body = alert.get("body") or {}
    details = body.get("details") if isinstance(body, dict) else None
    if details is not None:
        bits.append("--- body.details ---")
        bits.append(json.dumps(details, indent=2, sort_keys=True))
    contexts = body.get("contexts") if isinstance(body, dict) else None
    if contexts:
        bits.append("")
        bits.append("--- body.contexts ---")
        bits.append(json.dumps(contexts, indent=2, sort_keys=True))
    return "\n".join(bits) or "(no body)"
