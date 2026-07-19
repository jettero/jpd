#!/usr/bin/env python
# coding: utf-8
"""_parse_snooze — durations and clock times (24h + 12h am/pm).

Clock-time cases are asserted by equivalence (9pm ≡ 21:00) with a 1s
tolerance, since both calls read datetime.now() and could straddle a
second boundary.
"""

import pytest

from jpd.query import _parse_snooze


def _close(a, b):
    return abs(a - b) <= 1


@pytest.mark.parametrize(
    "spec,secs",
    [
        ("3600", 3600),
        ("90m", 5400),
        ("7.5h", int(7.5 * 3600)),
        ("1h40s", 3640),
    ],
)
def test_durations(spec, secs):
    assert _parse_snooze(spec) == secs


@pytest.mark.parametrize(
    "twelve,twentyfour",
    [
        ("9pm", "21:00"),
        ("9PM", "21:00"),
        ("9 pm", "21:00"),
        ("9:30pm", "21:30"),
        ("9:30 PM", "21:30"),
        ("12am", "00:00"),
        ("12pm", "12:00"),
        ("7am", "07:00"),
        ("12:15am", "00:15"),
    ],
)
def test_twelve_hour_matches_twentyfour(twelve, twentyfour):
    assert _close(_parse_snooze(twelve), _parse_snooze(twentyfour))


def test_clock_time_is_within_a_day():
    # A wall-clock target is always in (0, 24h] — never the 1h duration fallback
    # unless it genuinely lands there.
    secs = _parse_snooze("9pm")
    assert 0 < secs <= 24 * 3600
