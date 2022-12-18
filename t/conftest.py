#!/usr/bin/env python
# coding: utf-8

import pytest
from mypd.config import PDC, get_config

@pytest.fixture
def user_config():
    return PDC
