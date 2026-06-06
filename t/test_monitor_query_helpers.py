#!/usr/bin/env python
# coding: utf-8

import pytest

from jpd.query import merge_incidents, move_alert, update_incident_title


class FakeResp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, put_payload=None, post_payload=None):
        self.put_calls = []
        self.post_calls = []
        self.put_payload = put_payload or {}
        self.post_payload = post_payload or {}

    def put(self, path, json=None):
        self.put_calls.append((path, json))
        return FakeResp(self.put_payload)

    def post(self, path, json=None, headers=None):
        self.post_calls.append((path, json, headers))
        return FakeResp(self.post_payload)


def test_merge_dry_run():
    path, req = merge_incidents("P1", ["P2", "P3"], dry_run=True)
    assert path == "incidents/P1/merge"
    assert req["method"] == "PUT"
    assert {x["id"] for x in req["json"]["source_incidents"]} == {"P2", "P3"}


def test_merge_filters_self_from_sources():
    sess = FakeSession(put_payload={"incident": {"id": "P1", "title": "x"}})
    merge_incidents("P1", ["P1", "P2"], sess=sess)
    body = sess.put_calls[0][1]
    ids = [x["id"] for x in body["source_incidents"]]
    assert ids == ["P2"]


def test_move_alert_dry_run():
    path, req = move_alert("A9", "P2", "P1", dry_run=True)
    assert path == "incidents/P2/alerts/A9"
    assert req["json"]["alert"]["incident"]["id"] == "P2"


def test_update_title_dry_run():
    path, req = update_incident_title("P1", "new title", dry_run=True)
    assert path == "incidents/P1"
    assert req["json"]["incident"]["title"] == "new title"


def test_update_title_executes():
    sess = FakeSession(put_payload={"incident": {"id": "P1", "title": "new title"}})
    out = update_incident_title("P1", "new title", sess=sess)
    assert out["id"] == "P1"
    path, body = sess.put_calls[0]
    assert path == "incidents/P1"
    assert body["incident"]["title"] == "new title"
