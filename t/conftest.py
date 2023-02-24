#!/usr/bin/env python
# coding: utf-8

import pytest
from jpd.config import JPDC

@pytest.fixture
def user_config():
    return JPDC
