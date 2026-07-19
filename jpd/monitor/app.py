"""MonitorApp shell — owns polling, auto-ack, EOS, data-changed Signal.

Per-screen UI and actions live in jpd/monitor/{home,incident,alert}.py.
Modals live in jpd/monitor/modals.py.
"""

import asyncio
import sys
from datetime import datetime, timezone

from textual import work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.signal import Signal

from jpd.config import JPDC
from jpd.monitor import actions as A
from jpd.monitor._log import get_logger, setup as setup_logging
from jpd.monitor.config import MonitorConfig
from jpd.monitor.filters import FilterModel
from jpd.monitor.home import HomeScreen
from jpd.monitor.modals import AutoExitModal, HelpModal
from jpd.query import _parse_snooze


log = get_logger("app")


_SPIN_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


def _most_recent_assignee_id(incident):
    """Return the assignee.id of the most-recent assignment, or None.

    PD does not document the ordering of `incident.assignments`, so we
    pick the entry with the maximum ISO8601 `at` (lexicographic compare
    is correct for ISO8601). Returns None for empty / malformed input.
    """
    assignments = incident.get("assignments") or []
    best = None
    for a in assignments:
        at = a.get("at") or ""
        if best is None or at > (best.get("at") or ""):
            best = a
    if best is None:
        return None
    return (best.get("assignee") or {}).get("id")


class MonitorApp(App):
    """The TUI shell. The default screen is HomeScreen; deeper screens
    (Incident, Alert) are pushed on top.

    All polling and background state lives here so it keeps running while
    the user is in a sub-view.
    """

    CSS = """
    /* Modals share this — the only widgets with framed boxes. */
    #modal-box {
        border: heavy $accent;
        padding: 1 2;
        width: 90%;
        max-width: 140;
        height: 80%;
    }
    #detail-title { text-style: bold; padding-bottom: 1; }
    #detail-scroll { height: 1fr; }
    #detail-body { padding: 0 1; }
    #detail-hint { padding-top: 1; color: $text-muted; text-style: italic; }
    /* Full-screen content widgets — leave a blank line under the Header
       so the first row doesn't smoosh against it. */
    #home-table { height: 1fr; margin-top: 1; }
    #incident-alerts { height: 1fr; }
    #alert-scroll { height: 1fr; margin-top: 1; }
    #alert-body { padding: 0 1; }
    /* InfoScreen — single scrollable column carrying both the incident
       summary block and the notes. Built that way so small terminals
       (tmux panes under ~25 rows) don't deadlock between competing
       fixed-height widgets. */
    #info-scroll { height: 1fr; margin-top: 1; }
    #info-body { padding: 0 1; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", priority=True, show=False),
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help"),
        Binding("A", "toggle_auto_ack", "Auto-ack"),
        Binding("r", "refresh_now", "Refresh"),
        # Claim the command_palette action so Textual doesn't auto-add a
        # ctrl+p binding (we map it to Esc, screen-level, instead, so it
        # doesn't fire when a modal is open).
        Binding("ctrl+shift+f12", "command_palette", show=False),
    ]

    def __init__(self):
        super().__init__()
        # Hook _handle_exception so render/event-loop crashes land in our
        # log file. Otherwise Textual catches them, panics quietly, and
        # exits — leaving JPD_MONITOR_LOG with no clue why.
        _orig_handle_exception = self._handle_exception

        def _logged_handle_exception(err):
            log.exception("Textual unhandled exception → app exit: %s", err)
            return _orig_handle_exception(err)

        self._handle_exception = _logged_handle_exception
        self.mon_cfg = MonitorConfig()
        # Restore the saved theme (ansi-dark renders against the terminal's
        # actual background). Persisted back on change; see _on_theme_changed.
        self.theme = self.mon_cfg.get("theme", default="ansi-dark") or "ansi-dark"
        self.filt = FilterModel(self.mon_cfg)
        self.incidents = []
        self.auto_ack = bool(self.mon_cfg.get("auto_ack", default=False))
        self._poll_task = None
        self._auto_exit_task = None
        # Scheduled (config) + one-off (this session) auto-exit conditions.
        self._exit_tasks = []
        self._oneoff_exits = []
        self.eos_secs = None
        self.eos_iso = None
        self.eos_summary = None
        self._cadence_mult = 1
        self.auto_ack_cap_seconds = 4 * 3600
        self.auto_ack_count = 0
        self.is_polling = False
        self._spin_idx = 0
        # Published after every successful _do_poll; screens subscribe in
        # on_mount and re-render against the new self.incidents.
        self.data_changed = Signal(self, name="data_changed")

    def compose(self) -> ComposeResult:
        # Default screen is empty — HomeScreen is pushed in on_mount.
        return iter(())

    async def on_mount(self):
        log.info("on_mount: theme=%s auto_ack=%s filter=%s",
                 self.theme, self.auto_ack, self.filt.description())
        self._refresh_title()
        await self.push_screen(HomeScreen())
        log.debug("HomeScreen pushed; stack=%s", [type(s).__name__ for s in self.screen_stack])
        self._poll_task = asyncio.create_task(self._poll_loop())
        self.set_interval(0.1, self._advance_spinner)
        # Subscribe post-init so the initial theme set in __init__ doesn't
        # trigger a config write.
        self.theme_changed_signal.subscribe(self, self._on_theme_changed)
        self._arm_exit_conditions()
        await self._refresh_eos()

    # ---- command palette -------------------------------------------------

    def get_system_commands(self, screen):
        for cmd in super().get_system_commands(screen):
            # Single-pane app — maximizing the focused widget does nothing
            # useful, it just clutters the palette.
            if cmd.title == "Maximize":
                continue
            yield cmd
        yield SystemCommand(
            "Auto-exit…",
            "View / add / clear scheduled and one-off auto-exit conditions",
            self._open_auto_exit_modal,
        )

    def _open_auto_exit_modal(self):
        self.push_screen(AutoExitModal())

    def _on_theme_changed(self, theme):
        name = getattr(theme, "name", None) or self.theme
        if name == self.mon_cfg.get("theme", default="ansi-dark"):
            return
        self.mon_cfg.set("theme", name)
        self.mon_cfg.write()
        log.info("theme -> %s (persisted to %s)", name, self.mon_cfg.write_path)

    # ---- title -----------------------------------------------------------

    def _refresh_title(self):
        spin = f"{_SPIN_FRAMES[self._spin_idx]} " if self.is_polling else ""
        flag = " ⚡AUTO-ACK ON" if self.auto_ack else ""
        counter = f"  [auto-acked: {self.auto_ack_count}]" if self.auto_ack_count else ""
        self.title = f"{spin}jpd monitor{flag}{counter}"

    def _advance_spinner(self):
        if not self.is_polling:
            return
        self._spin_idx = (self._spin_idx + 1) % len(_SPIN_FRAMES)
        self._refresh_title()
        # The screens manage their own sub_title (breadcrumb).

    # ---- polling ---------------------------------------------------------

    async def _poll_loop(self):
        log.info("poll loop starting")
        while True:
            try:
                await self._do_poll()
            except Exception as e:
                log.exception("poll loop error: %s", e)
                self.notify(f"poll error: {e}", severity="error")
            base = int(self.mon_cfg.get("poll_seconds", default=30) or 30)
            sleep_for = max(5, base * self._cadence_mult)
            log.debug("poll loop sleeping %ds (cadence_mult=%d)", sleep_for, self._cadence_mult)
            await asyncio.sleep(sleep_for)

    async def _do_poll(self):
        log.debug("poll: starting")
        try:
            kw = self.filt.as_query_kwargs()
        except ValueError as e:
            log.warning("poll: filter rejected: %s", e)
            self.notify(f"filter: {e}", severity="error")
            return
        log.debug("poll: fetch_incidents(%s)", kw)
        self.is_polling = True
        self._refresh_title()
        try:
            try:
                incidents = await A.fetch_incidents(kw, refresh=True)
            finally:
                self.is_polling = False
                self._refresh_title()
        except Exception as e:
            if _is_rate_limited(e):
                self._cadence_mult = min(8, self._cadence_mult * 2)
                log.warning("poll: 429, cadence_mult -> %d", self._cadence_mult)
                self.notify(f"throttled (429); backing off ×{self._cadence_mult}",
                            severity="warning")
            else:
                log.exception("poll: fetch failed: %s", e)
                self.notify(f"fetch: {e}", severity="error")
            return
        if self._cadence_mult > 1:
            self._cadence_mult = max(1, self._cadence_mult // 2)
            log.debug("poll: success, cadence_mult relaxed -> %d", self._cadence_mult)
        log.info("poll: got %d incidents", len(incidents or ()))
        self.incidents = incidents or []
        if self.auto_ack:
            acked = await self._auto_ack_sweep(self.incidents)
            if acked:
                # We mutated server state; the local list is stale. Refetch
                # so the UI shows what's actually true. Acked means acked.
                log.debug("auto-acked %d — refetching", acked)
                self.is_polling = True
                self._refresh_title()
                try:
                    incidents = await A.fetch_incidents(kw, refresh=True)
                    self.incidents = incidents or []
                except Exception as e:
                    log.exception("post-auto-ack refetch failed: %s", e)
                finally:
                    self.is_polling = False
                    self._refresh_title()
        try:
            self.data_changed.publish(None)
            log.debug("data_changed signal published")
        except Exception as e:
            log.exception("data_changed publish failed: %s", e)

    # ---- auto-ack --------------------------------------------------------

    def _auto_ack_snooze_seconds(self):
        if not self.eos_secs:
            return None
        return max(60, min(self.eos_secs, self.auto_ack_cap_seconds))

    async def _auto_ack_sweep(self, incidents):
        """Ack every currently-triggered incident. Returns the count.

        Idempotency is provided by the status check below — only triggered
        incidents are touched. We must NOT skip iids we've "seen before":
        an existing incident can go acknowledged → triggered again when a
        new alert fires under it, or when a snooze expires. The earlier
        "only_new" filter was a bug — a re-fired incident would be skipped
        forever, leading to PagerDuty escalating five minutes later.

        Caller responsibility: refetch after this returns >0. If we
        acked, the UI must show acked. There's no "skip the refetch to
        save a call" — that's how the regression keeps coming back.
        """
        secs = self._auto_ack_snooze_seconds()
        log.info("auto-ack sweep: snooze_secs=%s", secs)
        acked = 0
        for inc in incidents:
            iid = inc.get("id")
            if not iid:
                continue
            if inc.get("status") != "triggered":
                log.debug("auto-ack skip %s: status=%s", iid, inc.get("status"))
                continue
            mine = _most_recent_assignee_id(inc)
            if mine != JPDC.user_id:
                log.info("auto-ack skip %s: most-recent assignee is %s, not me (%s)",
                         iid, mine, JPDC.user_id)
                continue
            log.info("auto-ack: %s (snooze=%s)", iid, secs)
            try:
                if secs is None:
                    await A.ack(iid)
                else:
                    await A.snooze(iid, secs)
                acked += 1
            except Exception as e:
                log.exception("auto-ack failed for %s: %s", iid, e)
                self.notify(f"auto-ack failed for {iid}: {e}", severity="error")
        if acked:
            self.auto_ack_count += acked
            self._refresh_title()
            window = "no snooze (EOS unknown)" if secs is None else f"snooze {_pretty_secs(secs)}"
            log.info("auto-ack sweep done: %d acked (total %d) — %s", acked, self.auto_ack_count, window)
            self.notify(f"auto-ack: {acked} PD(s) — {window}", timeout=5)
        else:
            log.debug("auto-ack sweep: nothing to do")
        return acked

    # ---- EOS -------------------------------------------------------------

    async def _refresh_eos(self):
        override = self.mon_cfg.get("eos_override", default=None)
        if override:
            self.eos_secs = _parse_snooze(str(override))
            self.eos_iso = f"override:{override}"
            self.eos_summary = "override"
            log.info("EOS: override=%s -> %ds", override, self.eos_secs)
        else:
            la = int(self.mon_cfg.get("eos_lookahead_hours", default=36) or 36)
            try:
                secs, iso, summary = await A.resolve_eos(lookahead_hours=la)
            except Exception as e:
                log.exception("EOS lookup failed: %s", e)
                self.notify(f"EOS lookup failed: {e}", severity="warning")
                return
            self.eos_secs = secs
            self.eos_iso = iso
            self.eos_summary = summary
            log.info("EOS: oncalls secs=%s iso=%s via=%s", secs, iso, summary)
        self._arm_auto_exit()

    def _arm_auto_exit(self):
        if self._auto_exit_task is not None:
            self._auto_exit_task.cancel()
            self._auto_exit_task = None
            log.debug("EOS auto-exit: previous task cancelled")
        if not self.mon_cfg.get("eos_auto_exit", default=True):
            log.debug("EOS auto-exit: disabled in config")
            return
        if not self.eos_secs:
            log.debug("EOS auto-exit: no eos_secs, not arming")
            return
        grace = int(self.mon_cfg.get("eos_grace_minutes", default=15) or 15) * 60
        fire_in = max(1, self.eos_secs + grace)
        self._auto_exit_task = asyncio.create_task(self._auto_exit_after(fire_in))
        log.info("EOS auto-exit armed: fires in %ds (eos_secs=%s, grace=%ds)",
                 fire_in, self.eos_secs, grace)

    async def _auto_exit_after(self, seconds):
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        # We can't push_screen_wait from here (not a worker), so just notify
        # and exit. If the user wants to defer they can disable auto-exit
        # in config.
        self.notify("Shift ended — exiting.", severity="warning", timeout=8)
        await asyncio.sleep(8)
        self.exit()

    # ---- scheduled / one-off auto-exit -----------------------------------

    def exit_conditions(self):
        """Return armed exit conditions as (kind, spec, secs), soonest first.

        `kind` is "schedule" (persisted in config) or "one-off" (this session).
        Non-positive / unparsable specs are dropped. Recomputed on demand so
        the countdowns stay live.
        """
        out = []
        for spec in (self.mon_cfg.get("auto_exit", default=[]) or []):
            out.append(("schedule", str(spec)))
        for spec in self._oneoff_exits:
            out.append(("one-off", str(spec)))
        rows = []
        for kind, spec in out:
            try:
                secs = _parse_snooze(spec)
            except Exception as e:
                log.warning("exit condition %r unparsable: %s", spec, e)
                continue
            if not secs or secs < 1:
                continue
            rows.append((kind, spec, secs))
        rows.sort(key=lambda r: r[2])
        return rows

    def _arm_exit_conditions(self):
        for t in self._exit_tasks:
            t.cancel()
        self._exit_tasks = []
        for kind, spec, secs in self.exit_conditions():
            self._exit_tasks.append(
                asyncio.create_task(self._exit_after(secs, spec, kind))
            )
            log.info("auto-exit armed: %s %r -> fires in %ds", kind, spec, secs)

    async def _exit_after(self, seconds, spec, kind):
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        self.notify(f"Auto-exit ({kind}: {spec}) — exiting so PD can phone.",
                    severity="warning", timeout=8)
        await asyncio.sleep(8)
        self.exit()

    def add_exit_condition(self, spec, persist=False):
        """Add a schedule (persist=True) or one-off exit spec, then re-arm."""
        spec = str(spec).strip()
        if not spec:
            return
        if persist:
            sched = list(self.mon_cfg.get("auto_exit", default=[]) or [])
            if spec not in sched:
                sched.append(spec)
            self.mon_cfg.set("auto_exit", sched)
            self.mon_cfg.write()
        else:
            self._oneoff_exits.append(spec)
        self._arm_exit_conditions()

    def remove_exit_condition(self, kind, spec):
        """Remove one condition (matched by kind+spec), persisting if schedule."""
        if kind == "schedule":
            sched = [s for s in (self.mon_cfg.get("auto_exit", default=[]) or [])
                     if str(s) != spec]
            self.mon_cfg.set("auto_exit", sched)
            self.mon_cfg.write()
        else:
            try:
                self._oneoff_exits.remove(spec)
            except ValueError:
                pass
        self._arm_exit_conditions()

    def clear_exit_conditions(self):
        self._oneoff_exits = []
        self.mon_cfg.set("auto_exit", [])
        self.mon_cfg.write()
        self._arm_exit_conditions()

    # ---- global actions --------------------------------------------------

    def action_toggle_auto_ack(self):
        self.auto_ack = not self.auto_ack
        log.info("auto-ack toggled -> %s", self.auto_ack)
        self._refresh_title()
        if self.auto_ack:
            self.notify("auto-ack ON — sweeping…")
            self._sweep_on_activation()
        else:
            self.notify("auto-ack OFF")

    @work
    async def _sweep_on_activation(self):
        if not self.eos_secs:
            await self._refresh_eos()
        await self._auto_ack_sweep(self.incidents)
        await self._do_poll()

    def action_refresh_now(self):
        self._kick_poll()

    @work
    async def _kick_poll(self):
        await self._do_poll()

    def action_help(self):
        screen = self.screen
        screen_name = type(screen).__name__
        screen_bindings = list(getattr(screen, "BINDINGS", ()) or ())
        log.debug("help opened from %s", screen_name)
        self.push_screen(HelpModal(
            screen_name=screen_name,
            screen_bindings=screen_bindings,
            app_bindings=list(self.BINDINGS or ()),
            state_lines=self.help_state_lines(),
        ))

    def help_state_lines(self):
        lines = [
            f"filter: {self.filt.description()}",
            f"PDs visible: {len(self.incidents)}",
            f"auto-ack: {'ON' if self.auto_ack else 'OFF'}  (acked: {self.auto_ack_count})",
        ]
        if self.eos_iso:
            lines.append(f"EOS: {self.eos_iso}  ({self.eos_summary or '?'})")
        conds = self.exit_conditions()
        if conds:
            for kind, spec, secs in conds:
                lines.append(f"auto-exit: {spec}  [{kind}]  in {_pretty_secs(secs)}")
        else:
            lines.append("auto-exit: (none)")
        return lines


# ---- helpers -------------------------------------------------------------


def _pretty_secs(secs):
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        h, m = divmod(secs, 3600)
        m //= 60
        return f"{h}h{m:02d}m" if m else f"{h}h"
    d, rem = divmod(secs, 86400)
    h = rem // 3600
    return f"{d}d{h}h" if h else f"{d}d"


def _is_rate_limited(exc):
    status = None
    resp = getattr(exc, "response", None)
    if resp is not None:
        status = getattr(resp, "status_code", None) or getattr(resp, "status", None)
    if status is None:
        status = getattr(exc, "status", None)
    return status == 429


# ---- entry point ---------------------------------------------------------


def run(_args=None):
    # Wire up file-logging if the env var is set; otherwise stays silent.
    setup_logging()
    log.info("MonitorApp.run() entered")
    MonitorApp().run()
    log.info("MonitorApp.run() returned")
    # Clear the lingering frame so the next bash prompt isn't dropped in
    # the middle of whatever the TUI last drew.
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()
