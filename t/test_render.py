#!/usr/bin/env python
# coding: utf-8

import os
import re
import pytest

from jpd.render import incidents_to_text


def _set_width(cols):
    os.environ["COLUMNS"] = str(cols)


def test_incident_basic_line_contains_tags_atomically(incident_basic, monkeypatch):
    _set_width(80)
    out = incidents_to_text([incident_basic], show_service_info=False, show_alerts=False)

    lines = out.splitlines()
    assert lines, "expected at least one line of output"

    text = "\n".join(lines)
    assert "[triggered]" in text
    assert "[priority: P1]" in text
    assert "[oncall-user]" in text
    # Age is compact 1 or 2 units like [1m5s] or [45s] or [2h]
    assert re.search(r"\[[0-9]+(?:[smhd])(?:[0-9]+[smhd])?\]", text)

    # No single line should contain broken tags
    for line in lines:
        assert line.count("[") == line.count("]"), "unbalanced tag wrap in a single line"


def test_alerts_render_with_service_suppression(incident_with_alerts):
    _set_width(100)
    out = incidents_to_text([incident_with_alerts], show_service_info=True, show_alerts=True)
    lines = out.splitlines()

    text = "\n".join(lines)
    assert "db: Disk full" in text
    assert "Lorem Service: Sed do eiusmod tempor" not in text


@pytest.mark.parametrize("cols", [60, 72, 90])
def test_never_wrap_inside_square_bracket_tags(cols, incident_with_long_alert):
    _set_width(cols)
    out = incidents_to_text([incident_with_long_alert], show_service_info=True, show_alerts=True)
    for line in out.splitlines():
        assert line.count("[") == line.count("]"), (
            "word wrapping split a tag on this line: %r" % line
        )


def test_very_narrow_terminal_raises():
    _set_width(40)
    with pytest.raises(ValueError):
        incidents_to_text([], show_service_info=False, show_alerts=False)
