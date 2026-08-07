#!/usr/bin/env python
# coding: utf-8

from datetime import datetime, timedelta, timezone

import pytest

from jpd.monitor.app import _most_recent_assignee_id


def _assignment(user_id, at):
    return {"at": at, "assignee": {"id": user_id, "type": "user_reference"}}


def test_empty_assignments():
    assert _most_recent_assignee_id({"assignments": []}) is None


def test_missing_assignments_key():
    assert _most_recent_assignee_id({}) is None


def test_assignments_null():
    assert _most_recent_assignee_id({"assignments": None}) is None


def test_single_assignment():
    inc = {"assignments": [_assignment("UME", "2026-06-11T10:00:00Z")]}
    assert _most_recent_assignee_id(inc) == "UME"


def test_start_of_shift_other_then_me():
    """Previous on-call assigned earlier; I'm assigned newer.
    Most-recent is me → ackable."""
    inc = {"assignments": [
        _assignment("UPREV", "2026-06-11T08:00:00Z"),
        _assignment("UME",   "2026-06-11T19:00:00Z"),
    ]}
    assert _most_recent_assignee_id(inc) == "UME"


def test_end_of_shift_me_then_next():
    """I was assigned earlier; rotation handed off to next on-call.
    Most-recent is next, NOT me → not ackable."""
    inc = {"assignments": [
        _assignment("UME",   "2026-06-11T08:00:00Z"),
        _assignment("UNEXT", "2026-06-11T19:00:00Z"),
    ]}
    assert _most_recent_assignee_id(inc) == "UNEXT"


def test_order_independent_oldest_first():
    inc = {"assignments": [
        _assignment("UOLD", "2026-06-11T01:00:00Z"),
        _assignment("UMID", "2026-06-11T12:00:00Z"),
        _assignment("UNEW", "2026-06-11T23:00:00Z"),
    ]}
    assert _most_recent_assignee_id(inc) == "UNEW"


def test_order_independent_newest_first():
    inc = {"assignments": [
        _assignment("UNEW", "2026-06-11T23:00:00Z"),
        _assignment("UMID", "2026-06-11T12:00:00Z"),
        _assignment("UOLD", "2026-06-11T01:00:00Z"),
    ]}
    assert _most_recent_assignee_id(inc) == "UNEW"


def test_missing_at_treated_as_oldest():
    """An entry without `at` sorts least (empty string < any ISO8601)
    so it doesn't accidentally win as 'most recent'."""
    inc = {"assignments": [
        {"assignee": {"id": "UBROKEN"}},
        _assignment("UREAL", "2026-06-11T12:00:00Z"),
    ]}
    assert _most_recent_assignee_id(inc) == "UREAL"


def test_missing_assignee_returns_none_id():
    inc = {"assignments": [{"at": "2026-06-11T12:00:00Z"}]}
    assert _most_recent_assignee_id(inc) is None


# ---- snooze horizon ------------------------------------------------------
# The window auto-ack snoozes for: min(end-of-shift, 4h), where end-of-shift
# is the soonest of the PD-derived EOS and any armed auto-exit condition.
# Never past the point where we stop watching — PD must go back to phoning.


@pytest.fixture
def set_eos(monkeypatch, patched_actions):
    """Make resolve_eos report a handoff `secs` from now (absolute + duration)."""
    def _set(secs):
        end = datetime.now(timezone.utc) + timedelta(seconds=secs)
        iso = end.strftime("%Y-%m-%dT%H:%M:%SZ")

        async def _resolve_eos(*_a, **_kw):
            return (secs, iso, "primary")

        monkeypatch.setattr(patched_actions, "resolve_eos", _resolve_eos)
    return _set


def _near(got, want, slack=5):
    """Clock-derived seconds tick down between arrange and assert."""
    assert want - slack <= got <= want, f"{got} not within {slack}s under {want}"


@pytest.mark.anyio
async def test_long_shift_snoozes_the_4h_cap(patched_actions, fake_jpdc, cfg_path, set_eos):
    from jpd.monitor.app import MonitorApp

    set_eos(8 * 3600)
    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        _near(app._auto_ack_snooze_seconds(), 4 * 3600)


@pytest.mark.anyio
async def test_short_shift_snoozes_to_eos(patched_actions, fake_jpdc, cfg_path, set_eos):
    from jpd.monitor.app import MonitorApp

    set_eos(90 * 60)
    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        _near(app._auto_ack_snooze_seconds(), 90 * 60)


@pytest.mark.anyio
async def test_snooze_shrinks_as_the_shift_burns_down(patched_actions, fake_jpdc, cfg_path, set_eos):
    """The regression: EOS resolved once at mount used to stay 8h forever,
    so a sweep an hour before handoff still handed out a full 4h snooze."""
    from jpd.monitor.app import MonitorApp

    set_eos(8 * 3600)
    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        _near(app._auto_ack_snooze_seconds(), 4 * 3600)
        # Five hours of shift elapse — 3h left, under the cap.
        app.eos_at -= timedelta(hours=5)
        _near(app._auto_ack_snooze_seconds(), 3 * 3600)
        # Ten minutes left: snooze ten minutes, not four hours.
        app.eos_at -= timedelta(hours=2, minutes=50)
        _near(app._auto_ack_snooze_seconds(), 10 * 60)


@pytest.mark.anyio
async def test_auto_exit_schedule_caps_the_snooze(patched_actions, fake_jpdc, cfg_path,
                                                  write_cfg, set_eos):
    """A scheduled auto-exit is the real end of shift when it lands first —
    snoozing past it leaves PDs silent with nobody watching."""
    write_cfg(cfg_path, {"auto_exit": ["2h"]})
    from jpd.monitor.app import MonitorApp

    set_eos(8 * 3600)
    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        _near(app._auto_ack_snooze_seconds(), 2 * 3600)


@pytest.mark.anyio
async def test_schedule_alone_bounds_the_snooze(patched_actions, fake_jpdc, cfg_path, write_cfg):
    """No PD on-call entry resolves, but the user pinned the handoff."""
    write_cfg(cfg_path, {"auto_exit": ["45m"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        _near(app._auto_ack_snooze_seconds(), 45 * 60)


@pytest.mark.anyio
async def test_eos_wins_when_it_lands_before_the_schedule(patched_actions, fake_jpdc, cfg_path,
                                                          write_cfg, set_eos):
    write_cfg(cfg_path, {"auto_exit": ["6h"]})
    from jpd.monitor.app import MonitorApp

    set_eos(70 * 60)
    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        _near(app._auto_ack_snooze_seconds(), 70 * 60)


@pytest.mark.anyio
async def test_no_horizon_means_plain_ack(patched_actions, fake_jpdc, cfg_path):
    """Nothing known about the shift end → ack with no snooze at all."""
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app._auto_ack_snooze_seconds() is None
