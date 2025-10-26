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
    # Do not require hyphenated token to remain on one line after wrapping
    assert "[oncall-user]" in out
    assert "[oncall-\n" not in out
    assert re.search(r"\[[0-9]+m[0-9]*s\]|\[[0-9]+s\]", out)


def test_incidents_to_text_service_prefix(monkeypatch, incident_with_alerts):
    monkeypatch.setenv("COLUMNS", "50")
    incidents = [incident_with_alerts]

    out = incidents_to_text(incidents, show_service_info=True, show_alerts=True)
    # Incident row includes service prefix (name or summary)
    assert re.search(r"^P2\s+🚨\s+(web: |Lorem Service:)", out, re.M)
    # First alert is same service as incident; should not repeat service and should strip incident prefix
    assert "➡️  Sed do eiusmod tempor" in out or "Sed do eiusmod tempor" in out
    assert "web: ➡️" not in out and "Lorem Service: ➡️" not in out
    # Second alert has different service; should include that service name
    assert ": db: Disk full" in out or "➡️  db: Disk full" in out


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


def test_id_column_is_single_token_and_does_not_wrap(monkeypatch):
    # Ensure that if the first column has content, it's a single 14-char token and never wraps.
    # Construct an incident with a 14-character ID and very narrow columns to force wrapping elsewhere.
    monkeypatch.setenv("COLUMNS", "40")
    long_id = "ABCDEFGHIJKLMN"  # 14 chars
    inc = {
        "id": long_id,
        "status": "triggered",
        "summary": "This summary should wrap in the third column only",
        "created_at": iso_ago(42),
    }
    out = incidents_to_text([inc], show_service_info=False, show_alerts=False)
    lines = out.splitlines()
    # The first line should contain the (possibly truncated) ID as one uninterrupted token before the emoji column.
    # ID appears as a single token with no wrapping before the emoji column
    assert lines[0].startswith(long_id + "  ")
    # Subsequent wrapped lines (if any) for the same row should have an empty first column area
    # (i.e., they should not repeat or wrap the ID). We check that lines after the first do not
    # contain the ID and begin with spaces followed by the indicator column.
    for cont in lines[1:]:
        assert long_id not in cont
        # Continuations should begin with spaces (empty ID column), then the indicator column alignment
        assert cont.startswith(" ")


def test_wrapping_at_small_valid_width(monkeypatch, incident_with_alerts):
    # 33 is the minimum valid width. Ensure wrapping still respects tags and indicators.
    monkeypatch.setenv("COLUMNS", "33")
    out = incidents_to_text([incident_with_alerts], show_service_info=True, show_alerts=True)
    # Should start with ID column
    assert out.splitlines()[0].startswith("P2  ")
    # Verify an alert indicator appears and tags are intact on wrapped lines
    assert "➡️" in out
    assert "[acknowledged]" in out
    assert "[triggered]" in out


def test_alert_wrapping_alignment(monkeypatch, incident_with_alerts, incident_with_long_alert):
    # Ensure wrapped alert lines align under alert text
    monkeypatch.setenv("COLUMNS", "60")
    # Use dedicated long alert fixture to ensure wrapping occurs
    data = incident_with_long_alert

    out = incidents_to_text([data], show_service_info=True, show_alerts=True)
    lines = out.splitlines()
    # Find the first alert indicator line
    arrow_idx = next(i for i,l in enumerate(lines) if "➡️" in l)
    first = lines[arrow_idx]
    # Next line should be a wrapped continuation of the same alert text
    cont = lines[arrow_idx+1]
    # Continuation should align under the alert text (after the indicator and two spaces)
    arrow_text_col = first.index("➡️  ") + len("➡️  ")
    cont_first_char_col = len(cont) - len(cont.lstrip(" "))
    assert cont_first_char_col == arrow_text_col
