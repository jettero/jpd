#!/usr/bin/env python
# coding: utf-8

import pytest
import yaml
from jpd.config import JPDConfig
from datetime import datetime, timedelta, timezone

@pytest.fixture
def milk_config():
    return JPDConfig('t/data/milk.yaml')

@pytest.fixture
def gandalf_config():
    return JPDConfig('t/data/gandalf.yaml')


# ---- MonitorApp harness --------------------------------------------------
# Shared by every test that drives MonitorApp under Textual's pilot, so
# nothing touches PagerDuty (and nothing mutates live incident state).


@pytest.fixture
def anyio_backend():
    """Pin the anyio backend to asyncio — textual is asyncio-only."""
    return "asyncio"


@pytest.fixture
def incidents():
    """Incident list the stubbed fetch serves. Override per-module."""
    return []


@pytest.fixture
def patched_actions(monkeypatch, incidents):
    """Stub network-touching actions so the app boots cleanly."""
    import jpd.monitor.actions as A

    async def _fetch(*_a, **_kw):
        return list(incidents)

    async def _resolve_eos(*_a, **_kw):
        return (None, None, None)

    monkeypatch.setattr(A, "fetch_incidents", _fetch)
    monkeypatch.setattr(A, "resolve_eos", _resolve_eos)
    return A


@pytest.fixture
def fake_jpdc(monkeypatch):
    """Sidestep real config file reading."""
    class _FakeJPDC:
        api_key = "x"
        email = "x@x"
        user_id = "Uself"
        team_ids = ("Tteam",)

    monkeypatch.setattr("jpd.monitor.filters.JPDC", _FakeJPDC)
    monkeypatch.setattr("jpd.monitor.app.JPDC", _FakeJPDC)
    return _FakeJPDC


@pytest.fixture
def cfg_path(monkeypatch, tmp_path):
    """Point MonitorConfig at a throwaway file; return its path."""
    path = tmp_path / "monitor.yaml"
    from jpd.monitor.config import MonitorConfig

    orig_init = MonitorConfig.__init__

    def _init(self, locations=None):
        orig_init(self, locations=(str(path),))

    monkeypatch.setattr(MonitorConfig, "__init__", _init)
    return path


@pytest.fixture
def write_cfg():
    """Write a jpd.monitor config block to `cfg_path`."""
    def _write(path, monitor_block):
        path.write_text(yaml.safe_dump({"jpd": {"monitor": monitor_block}}))
    return _write


def _iso_ago(seconds):
    now = datetime.now(timezone.utc)
    dt = now - timedelta(seconds=seconds)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


@pytest.fixture
def incident_basic():
    return {
        "id": "P1",
        "status": "triggered",
        "summary": "Lorem ipsum dolor sit amet",
        "created_at": _iso_ago(65),
        "priority": {"name": "P1"},
        "assignments": [{"assignee": {"summary": "oncall-user"}}],
    }


@pytest.fixture
def incident_with_alerts():
    return {
        "id": "P2",
        "status": "acknowledged",
        "summary": "Consectetur adipiscing elit",
        "created_at": _iso_ago(5),
        "service": {"id": "svc1", "summary": "Lorem Service"},
        "alerts": [
            {
                "title": "Sed do eiusmod tempor",
                "status": "triggered",
                "created_at": _iso_ago(3),
                "service": {"id": "svc1", "summary": "Lorem Service"},
            },
            {
                "title": "Disk full",
                "status": "resolved",
                "created_at": _iso_ago(2),
                "service": {"id": "svc2", "summary": "db"},
            },
        ],
    }


@pytest.fixture
def incident_with_long_alert():
    """Incident with a very long alert summary to exercise wrapping."""
    return {
        "id": "P3",
        "status": "acknowledged",
        "summary": "Ut enim ad minim veniam",
        "created_at": _iso_ago(600),
        "service": {"id": "svcL", "summary": "Dolor Service"},
        "alerts": [
            {
                "title": (
                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
                    "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation "
                    "ullamco laboris nisi ut aliquip ex ea commodo consequat without breaking tags like [status: triggered] or URLs"
                ),
                "status": "triggered",
                "created_at": _iso_ago(590),
                "service": {"id": "svcL", "summary": "Dolor Service"},
            }
        ],
    }
