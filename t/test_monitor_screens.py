#!/usr/bin/env python
# coding: utf-8
"""Screen-transition smoke tests using Textual's pilot harness.

Mocks jpd.monitor.actions so we never touch PagerDuty. Asserts the
screen stack reaches the expected depths under drill-in / back keys.
"""

import pytest

# patched_actions / fake_jpdc / cfg_path / anyio_backend: t/conftest.py


@pytest.fixture
def fake_incident():
    return {
        "id": "PINC1",
        "title": "Disk full on db-1",
        "summary": "Disk full on db-1",
        "status": "triggered",
        "urgency": "high",
        "created_at": "2026-06-06T10:00:00Z",
        "service": {"id": "Ssvc1", "summary": "db"},
        "assignments": [
            {"at": "2026-06-06T10:00:00Z",
             "assignee": {"id": "Uself", "type": "user_reference", "summary": "me"}},
        ],
        "alerts": [
            {
                "id": "PALERT1",
                "summary": "disk 95%",
                "title": "disk 95%",
                "status": "triggered",
                "created_at": "2026-06-06T10:00:05Z",
                "service": {"id": "Ssvc1", "summary": "db"},
                "body": {"details": {"host": "db-1", "pct": 95}},
            },
        ],
    }


@pytest.fixture
def incidents(fake_incident):
    """What the stubbed fetch serves these screens."""
    return [fake_incident]


@pytest.mark.anyio
async def test_boots_to_home(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp
    from jpd.monitor.home import HomeScreen

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)
        assert app.incidents and app.incidents[0]["id"] == "PINC1"


@pytest.mark.anyio
async def test_right_arrow_drills_in_and_esc_goes_back(patched_actions, fake_jpdc, cfg_path):
    from jpd.monitor.app import MonitorApp
    from jpd.monitor.home import HomeScreen
    from jpd.monitor.incident import IncidentScreen
    from jpd.monitor.alert import AlertScreen

    app = MonitorApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Unpark + drill in to incident
        await pilot.press("down")
        await pilot.press("right")
        await pilot.pause()
        assert isinstance(app.screen, IncidentScreen)
        # Drill in to alert
        await pilot.press("down")
        await pilot.press("right")
        await pilot.pause()
        assert isinstance(app.screen, AlertScreen)
        # Esc twice back to Home
        await pilot.press("left")
        await pilot.pause()
        assert isinstance(app.screen, IncidentScreen)
        await pilot.press("left")
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen)


@pytest.mark.anyio
async def test_auto_ack_count_visible_during_drill(patched_actions, fake_jpdc, cfg_path, fake_incident):
    """Auto-ack happens app-level — drilling shouldn't stop it.

    We simulate a poll cycle that triggers the auto-ack path by toggling
    auto-ack ON while a triggered PD is present, then drilling in.
    """
    from jpd.monitor.app import MonitorApp
    from jpd.monitor.incident import IncidentScreen
    import jpd.monitor.actions as A

    acks = []

    async def _ack(iid):
        acks.append(iid)
        return {"_ok": True}

    async def _snooze(iid, secs):
        acks.append((iid, secs))
        return {"_ok": True}

    import unittest.mock
    with unittest.mock.patch.object(A, "ack", _ack), unittest.mock.patch.object(A, "snooze", _snooze):
        app = MonitorApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Toggle auto-ack ON via global binding (A)
            await pilot.press("A")
            await pilot.pause()
            assert app.auto_ack is True
            # Drill in
            await pilot.press("down")
            await pilot.press("right")
            await pilot.pause()
            assert isinstance(app.screen, IncidentScreen)
            # The activation sweep should have acked the triggered incident
            assert acks, "expected at least one ack during the activation sweep"
