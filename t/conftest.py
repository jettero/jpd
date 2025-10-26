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
        "summary": "Main DB outage",
        "created_at": _iso_ago(65),
        "priority": {"name": "P1"},
        "assignments": [{"assignee": {"summary": "oncall-user"}}],
    }


@pytest.fixture
def incident_with_alerts():
    return {
        "id": "P2",
        "status": "acknowledged",
        "summary": "Cache meltdown",
        "created_at": _iso_ago(5),
        "service": {"id": "svc1", "summary": "web"},
        "alerts": [
            {
                "title": "Cache meltdown: node A",
                "status": "triggered",
                "created_at": _iso_ago(3),
                "service": {"id": "svc1", "summary": "web"},
            },
            {
                "title": "Disk full",
                "status": "resolved",
                "created_at": _iso_ago(2),
                "service": {"id": "svc2", "summary": "db"},
            },
        ],
    }
