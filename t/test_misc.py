#!/usr/bin/env python
# coding: utf-8

from mypd.misc import parse_date

def test_parse_date():
    oda = parse_date('1 day ago')
    assert oda.startswith('20')
    assert 'T' in oda

    at_the_time_of_this_writing = parse_date('22/Feb/2023 23:22:21 EST')
    assert at_the_time_of_this_writing == '2023-02-23T04:22Z'
