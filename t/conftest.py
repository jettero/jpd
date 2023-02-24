#!/usr/bin/env python
# coding: utf-8

import pytest
from jpd.config import JPDConfig

@pytest.fixture
def milk_config():
    return JPDConfig('t/data/milk.yaml')

@pytest.fixture
def gandalf_config():
    return JPDConfig('t/data/gandalf.yaml')
