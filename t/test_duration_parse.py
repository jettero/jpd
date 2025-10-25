#!/usr/bin/env python
# coding: utf-8

import pytest

from jpd.query import duration_parse


@pytest.mark.parametrize(
    "dstr,dur",
    [
        ("4k", 4000),
        ("4ks", 4000),
        ("4ksec", 4000),
        ("4KSEC", 4000),
        ("3600", 3600),
        ("60m", 3600),
        ("1h", 3600),
        ("1h32m", 3600 + 32 * 60),
        ("2d1h", 2 * 86400 + 3600),
        ("90m", 90 * 60),
        ("1h40s", 3600 + 40),
        (4000, 4000),  # support non-str inputs via str() in parser
    ],
)
def test_duration_parse_parametrized(dstr, dur):
    assert duration_parse(dstr) == dur


def test_unparsable_defaults_to_one_hour():
    assert duration_parse("nonsense") == 3600
