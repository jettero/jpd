#!/usr/bin/env python
# coding: utf-8

import os
import re
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from jpd.render import incidents_to_text, tag_safe_wrap, strip_incident_prefix


def iso_ago(seconds):
    now = datetime.now(timezone.utc)
    dt = now - timedelta(seconds=seconds)
    # keep seconds precision small to avoid flakiness
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_tag_safe_wrap_preserves_bracket_tags():
    tw = textwrap.TextWrapper(width=20, break_long_words=False, break_on_hyphens=False)
    text = "alpha [status: triggered] bravo"
    wrapped = tag_safe_wrap(tw, text)
    joined = "\n".join(wrapped)
    assert "[status: triggered]" in joined
    assert "[status:\ntriggered]" not in joined


def test_strip_incident_prefix_variants():
    assert strip_incident_prefix("Foo: extra", "Foo") == "extra"
    assert strip_incident_prefix("Foo - extra", "Foo") == "extra"
    # en dash currently not treated as a removable delimiter in implementation
    assert strip_incident_prefix("Foo – extra", "Foo") == "– extra"
    # em dash currently not treated as a removable delimiter
    assert strip_incident_prefix("Foo — extra", "Foo") == "— extra"
    assert strip_incident_prefix("Foo|extra", "Foo") == "extra"
    # no change when not a prefix
    assert strip_incident_prefix("Something else", "Foo") == "Something else"


def test_incidents_to_text_basic_alignment(monkeypatch, incident_basic):
    monkeypatch.setenv("COLUMNS", "60")
    incidents = [incident_basic]

    out = incidents_to_text(incidents, show_service_info=False, show_alerts=False)
    lines = out.splitlines()
    assert lines[0].startswith("P1  ")
    assert "[triggered]" in out
    assert "[priority: P1]" in out
    assert "[oncall-user]" in out
    assert re.search(r"\[[0-9]+m[0-9]*s\]|\[[0-9]+s\]", out)


def test_incidents_to_text_service_prefix(monkeypatch, incident_with_alerts):
    monkeypatch.setenv("COLUMNS", "50")
    incidents = [incident_with_alerts]

    out = incidents_to_text(incidents, show_service_info=True, show_alerts=True)
    # Incident row includes service prefix
    assert re.search(r"^P2\s+web: ", out, re.M)
    # First alert is same service as incident; should not repeat service and should strip incident prefix
    assert "• node A" in out
    assert "web: •" not in out
    # Second alert has different service; should include that service name
    assert ": db: Disk full" in out or "• db: Disk full" in out


def test_incidents_to_text_no_alerts(monkeypatch, incident_with_alerts):
    monkeypatch.setenv("COLUMNS", "40")
    # reuse fixture and just toggle show_alerts; content should not include bullets
    incidents = [incident_with_alerts]
    out = incidents_to_text(incidents, show_service_info=False, show_alerts=False)
    # Should not include bullet alert lines when show_alerts is False
    assert "•" not in out


def test_narrow_width_raises(monkeypatch, incident_basic):
    # any less than 33 should raise
    monkeypatch.setenv("COLUMNS", "32")
    with pytest.raises(ValueError):
        incidents_to_text([incident_basic], show_service_info=False, show_alerts=False)


def test_wrapping_at_small_valid_width(monkeypatch, incident_with_alerts):
    # 33 is the minimum valid width. Ensure wrapping still respects tags and bullets.
    monkeypatch.setenv("COLUMNS", "33")
    out = incidents_to_text([incident_with_alerts], show_service_info=True, show_alerts=True)
    # Should start with ID column
    assert out.splitlines()[0].startswith("P2  ")
    # Verify a bullet line appears and tags are intact on wrapped lines
    assert "•" in out
    assert "[acknowledged]" in out
    assert "[triggered]" in out
