#!/usr/bin/env python
# coding: utf-8

from datetime import datetime, timezone, timedelta
import pytest

from jpd.query import list_my_oncall_until


class FakeSession:
    def __init__(self, entries):
        self.entries = entries
        self.calls = []

    def list_all(self, path, params=None):
        self.calls.append((path, params))
        return list(self.entries)


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def now_dt():
    return datetime(2026, 6, 4, 14, 0, 0, tzinfo=timezone.utc)


def test_picks_current_shift(now_dt):
    end = now_dt + timedelta(hours=5)
    sess = FakeSession([
        {"start": _iso(now_dt - timedelta(hours=2)), "end": _iso(end),
         "schedule": {"id": "S1", "summary": "primary"}},
    ])
    secs, iso, summary = list_my_oncall_until(user_id="U", sess=sess, _now=now_dt)
    assert secs == 5 * 3600
    assert iso == _iso(end)
    assert summary == "primary"


def test_picks_earliest_end_on_overlap(now_dt):
    end_a = now_dt + timedelta(hours=2)
    end_b = now_dt + timedelta(hours=8)
    sess = FakeSession([
        {"start": _iso(now_dt - timedelta(hours=1)), "end": _iso(end_b),
         "schedule": {"summary": "secondary"}},
        {"start": _iso(now_dt - timedelta(hours=1)), "end": _iso(end_a),
         "schedule": {"summary": "primary"}},
    ])
    secs, iso, summary = list_my_oncall_until(user_id="U", sess=sess, _now=now_dt)
    assert secs == 2 * 3600
    assert summary == "primary"


def test_no_current_shift(now_dt):
    future_start = now_dt + timedelta(hours=2)
    sess = FakeSession([
        {"start": _iso(future_start), "end": _iso(future_start + timedelta(hours=1)),
         "schedule": {"summary": "future"}},
    ])
    secs, iso, summary = list_my_oncall_until(user_id="U", sess=sess, _now=now_dt)
    assert secs is None
    assert iso is None
    assert summary is None


def test_handles_z_suffix(now_dt):
    end = now_dt + timedelta(hours=3)
    sess = FakeSession([
        {"start": (now_dt - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
         "schedule": {"summary": "z-suffix"}},
    ])
    secs, _, _ = list_my_oncall_until(user_id="U", sess=sess, _now=now_dt)
    assert secs == 3 * 3600


def test_request_shape(now_dt):
    sess = FakeSession([])
    list_my_oncall_until(user_id="UFOO", lookahead_hours=12, sess=sess, _now=now_dt)
    assert sess.calls
    path, params = sess.calls[0]
    assert path == "oncalls"
    assert params["user_ids[]"] == ["UFOO"]
    assert params["earliest"] == "true"
    assert params["since"] == _iso(now_dt)
    assert params["until"] == _iso(now_dt + timedelta(hours=12))
