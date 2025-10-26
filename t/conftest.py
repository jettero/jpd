#!/usr/bin/env python
# coding: utf-8

import pytest
from jpd.config import JPDConfig
from datetime import datetime, timedelta, timezone

@pytest.fixture
def milk_config():
    return JPDConfig('t/data/milk.yaml')

@pytest.fixture
def gandalf_config():
    return JPDConfig('t/data/gandalf.yaml')


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
