#!/usr/bin/env python
# coding: utf-8

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
