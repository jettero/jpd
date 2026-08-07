#!/usr/bin/env python
# coding: utf-8
"""Auto-exit conditions, theme persistence, and command-palette tweaks.

Drives MonitorApp under Textual's pilot harness with actions stubbed, so
nothing touches PagerDuty (and nothing mutates live incident state).
"""

import pytest

# patched_actions / fake_jpdc / cfg_path / write_cfg / anyio_backend: t/conftest.py


# ---- command palette -----------------------------------------------------


@pytest.mark.anyio
async def test_palette_drops_maximize_adds_auto_exit(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        titles = [c.title for c in app.get_system_commands(app.screen)]
        assert "Maximize" not in titles
        assert "Auto-exit…" in titles


# ---- theme persistence ---------------------------------------------------


@pytest.mark.anyio
async def test_theme_change_persists(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.theme = "nord"
        await pilot.pause()
        assert app.mon_cfg.get("theme") == "nord"

    # Round-trip: a fresh config reads it back off disk.
    from jpd.monitor.config import MonitorConfig
    assert MonitorConfig().get("theme") == "nord"


@pytest.mark.anyio
async def test_saved_theme_restored_on_launch(patched_actions, fake_jpdc, cfg_path, write_cfg):
    write_cfg(cfg_path, {"theme": "gruvbox"})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    assert app.theme == "gruvbox"
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "gruvbox"


# ---- exit-conditions engine ----------------------------------------------


@pytest.mark.anyio
async def test_schedule_from_config_is_armed(patched_actions, fake_jpdc, cfg_path, write_cfg):
    write_cfg(cfg_path, {"auto_exit": ["2h", "30m"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        conds = app.exit_conditions()
        # Soonest first: 30m before 2h.
        assert [c[1] for c in conds] == ["30m", "2h"]
        assert all(kind == "schedule" for kind, _, _ in conds)
        assert len(app._exit_tasks) == 2


@pytest.mark.anyio
async def test_add_oneoff_and_schedule(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.add_exit_condition("45m", persist=False)
        app.add_exit_condition("21:00", persist=True)
        await pilot.pause()

        kinds = {spec: kind for kind, spec, _ in app.exit_conditions()}
        assert kinds["45m"] == "one-off"
        assert kinds["21:00"] == "schedule"

        # Only the schedule entry is persisted; the one-off is session-only.
        assert app.mon_cfg.get("auto_exit") == ["21:00"]
        from jpd.monitor.config import MonitorConfig
        assert MonitorConfig().get("auto_exit") == ["21:00"]


@pytest.mark.anyio
async def test_remove_and_clear(patched_actions, fake_jpdc, cfg_path, write_cfg):
    write_cfg(cfg_path, {"auto_exit": ["2h"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app.add_exit_condition("10m", persist=False)
        await pilot.pause()
        assert len(app.exit_conditions()) == 2

        app.remove_exit_condition("schedule", "2h")
        await pilot.pause()
        assert [c[1] for c in app.exit_conditions()] == ["10m"]
        assert app.mon_cfg.get("auto_exit") == []

        app.clear_exit_conditions()
        await pilot.pause()
        assert app.exit_conditions() == []
        assert app._exit_tasks == []


@pytest.mark.anyio
async def test_bad_spec_is_dropped(patched_actions, fake_jpdc, cfg_path, write_cfg):
    # duration_parse falls back to 3600 for pure-nonsense, but an explicitly
    # zero/negative-seconds spec must not arm. "0s" -> 0 -> dropped.
    write_cfg(cfg_path, {"auto_exit": ["0s", "1h"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert [c[1] for c in app.exit_conditions()] == ["1h"]


@pytest.mark.anyio
async def test_add_rejects_unparseable(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.add_exit_condition("tonite", persist=False) is False
        assert app.add_exit_condition("9p", persist=True) is False
        assert app.add_exit_condition("0s", persist=False) is False  # degenerate
        await pilot.pause()
        # Nothing armed, nothing persisted, nothing added to one-offs.
        assert app.exit_conditions() == []
        assert app._oneoff_exits == []
        assert app.mon_cfg.get("auto_exit") == []


@pytest.mark.anyio
async def test_bad_config_entry_skipped_not_coerced(patched_actions, fake_jpdc, cfg_path, write_cfg):
    # A hand-edited typo must NOT silently arm a 1h timer — it's skipped.
    write_cfg(cfg_path, {"auto_exit": ["tonite", "9pm"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        specs = [c[1] for c in app.exit_conditions()]
        assert specs == ["9pm"]
        assert len(app._exit_tasks) == 1


# ---- management modal ----------------------------------------------------


@pytest.mark.anyio
async def test_modal_add_oneoff_via_input(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp
    from jpd.monitor.modals import AutoExitModal

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._open_auto_exit_modal()
        await pilot.pause()
        assert isinstance(app.screen, AutoExitModal)
        # No schedule → first row is "Add one-off timer…"; activate it.
        await pilot.press("enter")
        await pilot.pause()
        # InputModal is now on top; type a spec and submit.
        await pilot.press("1", "5", "m")
        await pilot.press("enter")
        await pilot.pause()
        assert "15m" in [c[1] for c in app.exit_conditions()]
        assert app.mon_cfg.get("auto_exit") == []  # one-off, not persisted


@pytest.mark.anyio
async def test_modal_d_removes_condition(patched_actions, fake_jpdc, cfg_path, write_cfg):
    write_cfg(cfg_path, {"auto_exit": ["2h"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        app._open_auto_exit_modal()
        await pilot.pause()
        # Highlighted row is the "2h" condition; `d` removes it.
        await pilot.press("d")
        await pilot.pause()
        assert app.exit_conditions() == []
        assert app.mon_cfg.get("auto_exit") == []


@pytest.mark.anyio
async def test_help_lists_auto_exit(patched_actions, fake_jpdc, cfg_path, write_cfg):
    write_cfg(cfg_path, {"auto_exit": ["3h"]})
    from jpd.monitor.app import MonitorApp

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        lines = app.help_state_lines()
        assert any("auto-exit: 3h" in ln and "schedule" in ln for ln in lines)
