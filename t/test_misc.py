#!/usr/bin/env python
# coding: utf-8

import pytest
import jpd.misc as m
import jpd.const as c

def test_parse_date():
    oda = m.parse_date('1 day ago')
    assert oda.startswith('20')
    assert 'T' in oda
    assert oda[-1] == 'Z'

    at_the_time_of_this_writing = m.parse_date('22/Feb/2023 23:22:21 EST')
    assert at_the_time_of_this_writing == '2023-02-23T04:22Z'
    assert at_the_time_of_this_writing.endswith('Z')

def test_aliases_and_colloquialisms(context=None):
    kw = dict()
    if context:
        kw['context'] = context
    assert set(m.aliases_and_colloquialisms('supz', 'mang', **kw)) == set(('mang', 'supz'))
    assert set(m.aliases_and_colloquialisms('supz', 'mang', 'any', **kw)) == set(('mang', 'supz', None))

    # any should short circut ... it means: don't provide this param for most fields
    assert set(m.aliases_and_colloquialisms('any', 'supz', 'mang', 'any', **kw)) == set((None,))
    assert set(m.aliases_and_colloquialisms('any', 'supz', 'mang', 'any', **kw)) == set((None,))

    assert set(m.aliases_and_colloquialisms('all', 'supz', 'mang', 'all', **kw)) == set((None,))
    assert set(m.aliases_and_colloquialisms('all', 'supz', 'mang', 'all', **kw)) == set((None,))

def test_aliases_and_colloquialisms_context_user():
    test_aliases_and_colloquialisms(context='user')

def test_aliases_and_colloquialisms_context_team():
    test_aliases_and_colloquialisms(context='team')

def test_aliases_and_colloquialisms_context_status():
    with pytest.raises(c.StatusesException):
        test_aliases_and_colloquialisms(context='status')

def test_aliases_and_colloquialisms_context_include():
    with pytest.raises(c.IncludesException):
        test_aliases_and_colloquialisms(context='include')

def test_aliases_and_colloquialisms_context_dumb():
    with pytest.raises(c.ContextsException):
        test_aliases_and_colloquialisms(context='dumb')

def test_split_strings_maybe(context=None):
    kw = dict()
    if context:
        kw['context'] = context
    assert m.split_strings_maybe('this is a test', **kw) == list(sorted(('this', 'is', 'a', 'test')))
