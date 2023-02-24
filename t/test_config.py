#!/usr/bin/env python
# coding: utf-8

import tempfile
import pytest

def test_milk_config(milk_config):
    assert '@guhmail' in milk_config.email
    assert 'milk' in milk_config.email
    assert hasattr(milk_config, 'team_ids')
    assert not hasattr(milk_config, 'team_id')
    assert 'milky-whites' in milk_config.team_ids
    assert milk_config.user_id == 'milky-white-01'

def test_gandalf_config(gandalf_config):
    assert '@guhmail' in gandalf_config.email
    assert 'gandalf' in gandalf_config.email
    assert 'MAIAR' in gandalf_config.team_ids
    assert 'FELLOWSHIP' in gandalf_config.team_ids
