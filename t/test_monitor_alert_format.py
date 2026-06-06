#!/usr/bin/env python
# coding: utf-8
"""Tests for jpd.monitor.alert_format.

We check the *rendered* plain-text output (Text.plain) and that the
styling map contains specific style spans we care about (URLs underlined,
status tokens colored, link-shape labels styled). We do NOT pin specific
column positions — just structural assertions.
"""

import pytest

from jpd.monitor.alert_format import format_alert


def _styles_in(text):
    """Return all rendered Rich style strings present in a Text object."""
    return {str(span.style) for span in text.spans if span.style}


def _links_in(text):
    """Return the set of OSC-8 link URLs attached to spans of a Text."""
    links = set()
    for span in text.spans:
        style = span.style
        link = getattr(style, "link", None) if style is not None else None
        if link:
            links.add(link)
    return links


@pytest.fixture
def alert_basic():
    return {
        "id": "PALERT1",
        "status": "triggered",
        "created_at": "2026-06-06T10:00:00Z",
        "html_url": "https://example.pagerduty.com/alerts/PALERT1",
        "service": {"summary": "db", "id": "Sdb"},
        "summary": "Disk full on db-1",
        "body": {
            "details": {
                "host": "db-1",
                "pct_used": 95,
                "notes": "Triggered when disk crosses warning threshold.",
            },
        },
    }


def test_header_includes_known_fields(alert_basic):
    out = format_alert(alert_basic)
    plain = out.plain
    assert "PALERT1" in plain
    assert "triggered" in plain
    assert "Disk full on db-1" in plain
    assert "db" in plain
    assert "https://example.pagerduty.com/alerts/PALERT1" in plain


def test_status_token_is_styled_red(alert_basic):
    out = format_alert(alert_basic)
    styles = _styles_in(out)
    assert any("red" in s for s in styles), f"expected red styling in {styles}"


def test_link_shape_renders_as_clickable_hyperlink():
    """Link shape becomes an OSC-8 hyperlink: visible text only, the URL
    rides in the style's `link` attribute so terminals like iTerm2 and
    WezTerm render it as a clickable label."""
    alert = {
        "id": "PA", "status": "triggered",
        "body": {
            "contexts": [
                {"type": "link", "href": "https://grafana.example.com/d/abc",
                 "text": "Grafana dashboard"},
            ],
        },
    }
    out = format_alert(alert)
    assert "Grafana dashboard" in out.plain
    # URL must NOT be in the visible text — that's the whole point.
    assert "https://grafana.example.com/d/abc" not in out.plain
    # …but must be present as an OSC-8 link on at least one span.
    assert "https://grafana.example.com/d/abc" in _links_in(out)
    assert any("underline" in s for s in _styles_in(out))


def test_image_shape_renders_clickable_marker():
    alert = {
        "id": "PA", "status": "triggered",
        "body": {
            "contexts": [
                {"type": "image", "src": "https://example.com/x.png",
                 "alt": "graph"},
            ],
        },
    }
    out = format_alert(alert)
    assert "[image]" in out.plain
    assert "graph" in out.plain
    # Src is the clickable target, not visible text.
    assert "https://example.com/x.png" not in out.plain
    assert "https://example.com/x.png" in _links_in(out)


def test_url_in_string_value_is_clickable():
    """When the URL appears inline in a string, the URL itself is the
    visible text — and a click-link is attached so it's actionable."""
    alert = {
        "id": "PA", "status": "triggered",
        "body": {
            "details": {"runbook": "see https://runbooks.example.com/disk-full"},
        },
    }
    out = format_alert(alert)
    assert "https://runbooks.example.com/disk-full" in out.plain
    assert "https://runbooks.example.com/disk-full" in _links_in(out)
    assert any("underline" in s for s in _styles_in(out))


def test_nested_dict_keys_are_styled():
    alert = {
        "id": "PA", "status": "triggered",
        "body": {"details": {"host": "db-1", "metrics": {"cpu": 99, "mem": 87}}},
    }
    out = format_alert(alert)
    styles = _styles_in(out)
    assert any("cyan" in s and "bold" in s for s in styles), (
        f"expected bold+cyan key styling, got {styles}"
    )


def test_html_string_is_textified():
    alert = {
        "id": "PA", "status": "triggered",
        "body": {
            "details": {
                "msg": '<!DOCTYPE html><html><body><p>plain text body</p></body></html>',
            },
        },
    }
    out = format_alert(alert)
    assert "plain text body" in out.plain
    # Raw HTML markers should be stripped.
    assert "<html>" not in out.plain
    assert "<!DOCTYPE" not in out.plain


def test_no_body_renders_minimal():
    alert = {"id": "PA", "status": "resolved"}
    out = format_alert(alert)
    assert "PA" in out.plain
    assert "resolved" in out.plain
