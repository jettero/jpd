#!/usr/bin/env python
# coding: utf-8

from datetime import datetime, timezone, timedelta
import pytest

import jpd.query
from jpd.query import list_audit_records, filter_audit_records, my_schedule_ids
from jpd.render import build_audit_rows, audit_records_to_text, _colorize_audit_text


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


# ---- list_audit_records: server-side param assembly (dry-run, no session) ----

def test_audit_dry_run_param_assembly():
    path, params = list_audit_records(
        since="2023-01-01",
        until="2023-01-02",
        root_resource_types=["schedules"],
        actions=["update", "delete"],
        actor_id="U1",
        dry_run=True,
    )
    assert path == "audit/records"
    assert params["root_resource_types[]"] == ["schedules"]
    assert params["actions[]"] == ["update", "delete"]
    assert params["actor_id"] == "U1"
    # parse_date -> ISO8601 with a trailing Z
    assert params["since"].endswith("Z")
    assert params["until"].endswith("Z")


def test_audit_dry_run_omits_unset_filters():
    path, params = list_audit_records(dry_run=True)
    assert path == "audit/records"
    for k in ("since", "until", "root_resource_types[]", "actions[]", "actor_id", "actor_type"):
        assert k not in params


def _passthrough_cache(f, *a, cache_dir=None, cache_group=None, refresh=False, auto_pick=None, **kw):
    # stand-in for auto_cache: call the underlying fetch directly, dropping
    # auto_cache's own bookkeeping kwargs before delegating.
    return f(*a, **kw)


class FakeCursorSession:
    """Mimics pagerduty 6.2.1: list_all returns [] for cursor endpoints (broken),
    while iter_cursor paginates correctly and raises on HTTP errors."""

    def __init__(self, records, raise_exc=None):
        self.records = records
        self.raise_exc = raise_exc
        self.cursor_calls = []

    def list_all(self, path, params=None):
        return []  # the upstream cursor bug we must NOT rely on

    def iter_cursor(self, path, params=None):
        self.cursor_calls.append((path, params))
        if self.raise_exc is not None:
            raise self.raise_exc
        return iter(list(self.records))


def test_audit_uses_cursor_not_list_all(monkeypatch):
    # Regression: list_all silently returns [] for cursor endpoints in
    # pagerduty 6.2.1, so the scanner must page via iter_cursor.
    monkeypatch.setattr(jpd.query, "auto_cache", _passthrough_cache)
    recs = [{"id": "R1"}, {"id": "R2"}]
    sess = FakeCursorSession(recs)
    out = list_audit_records(actions=["create"], sess=sess)
    assert out == recs
    path, params = sess.cursor_calls[0]
    assert path == "audit/records"
    assert params["actions[]"] == ["create"]


def test_audit_surfaces_http_error(monkeypatch):
    # Regression: a 403 (Access Denied) must propagate, not be swallowed into
    # an empty "No audit records" result.
    monkeypatch.setattr(jpd.query, "auto_cache", _passthrough_cache)
    boom = RuntimeError("API responded with client error (status 403)")
    sess = FakeCursorSession([], raise_exc=boom)
    with pytest.raises(RuntimeError):
        list_audit_records(sess=sess)


# ---- filter_audit_records: client-side post-filter ----

def _rec(rid, resource_id, actor_ids=()):
    return {
        "id": rid,
        "root_resource": {"id": resource_id, "type": "schedule_reference", "summary": resource_id},
        "actors": [{"id": a} for a in actor_ids],
        "action": "update",
    }


def test_filter_by_resource_ids():
    records = [_rec("R1", "S1"), _rec("R2", "S2"), _rec("R3", "S1")]
    kept = filter_audit_records(records, resource_ids=["S1"])
    assert {r["id"] for r in kept} == {"R1", "R3"}


def test_filter_by_actor():
    records = [_rec("R1", "S1", ["U1"]), _rec("R2", "S1", ["U2"]), _rec("R3", "S1", ["U1", "U2"])]
    kept = filter_audit_records(records, actor_id="U1")
    assert {r["id"] for r in kept} == {"R1", "R3"}


def test_filter_no_criteria_keeps_all():
    records = [_rec("R1", "S1"), _rec("R2", "S2")]
    assert filter_audit_records(records) == records


# ---- my_schedule_ids: forward-looking oncalls window ----

def test_my_schedule_ids_forward_window(now_dt):
    end = now_dt + timedelta(hours=5)
    sess = FakeSession([
        {"start": _iso(now_dt), "end": _iso(end), "schedule": {"id": "S1"}},
        {"start": _iso(now_dt), "end": _iso(end), "schedule": {"id": "S1"}},
        {"start": _iso(now_dt), "end": _iso(end), "schedule": {"id": "S2"}},
    ])
    ids = my_schedule_ids(user_id="U", sess=sess, _now=now_dt)
    assert ids == ["S1", "S2"]
    path, params = sess.calls[0]
    assert path == "oncalls"
    assert params["user_ids[]"] == ["U"]
    # window starts at now (no lookback) and ends now+90d by default
    assert params["since"] == _iso(now_dt)
    assert params["until"] == _iso(now_dt + timedelta(days=90))


def test_my_schedule_ids_empty(now_dt):
    sess = FakeSession([])
    assert my_schedule_ids(user_id="U", sess=sess, _now=now_dt) == []


# ---- rendering ----

def test_build_audit_rows_shape():
    rec = {
        "id": "PXXXXXX",
        "execution_time": "2026-06-04T12:00:00Z",
        "actors": [{"id": "U1", "summary": "alice@example.com"}],
        "root_resource": {"id": "S1", "type": "schedules", "summary": "Primary On-Call"},
        "action": "update",
    }
    rows = build_audit_rows([rec])
    assert len(rows) == 1
    rid, sym, text = rows[0]
    assert rid == "PXXXXXX"
    assert sym == "~"
    assert "schedules: Primary On-Call" in text
    assert "[update]" in text
    assert "[alice@example.com]" in text


def test_audit_records_to_text_layout(monkeypatch):
    monkeypatch.setenv("COLUMNS", "80")
    rec = {
        "id": "PXXXXXX",
        "execution_time": "2026-06-04T12:00:00Z",
        "actors": [{"id": "U1", "summary": "alice"}],
        "root_resource": {"id": "S1", "type": "schedules", "summary": "Primary On-Call"},
        "action": "update",
    }
    out = audit_records_to_text([rec], color="never")
    assert "schedules: Primary On-Call" in out
    assert "[update]" in out
    for line in out.splitlines():
        assert line.count("[") == line.count("]"), "unbalanced tag wrap"


def test_audit_records_to_text_empty():
    assert audit_records_to_text([]) == "No audit records."


def test_audit_colorize_actions():
    assert "\x1b[32m[create]\x1b[0m" in _colorize_audit_text("x [create] y", True)
    assert "\x1b[33m[update]\x1b[0m" in _colorize_audit_text("x [update] y", True)
    assert "\x1b[31m[delete]\x1b[0m" in _colorize_audit_text("x [delete] y", True)
    # disabled -> untouched
    assert _colorize_audit_text("x [create] y", False) == "x [create] y"
