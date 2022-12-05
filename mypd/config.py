#!/usr/bin/env python
# coding: utf-8

import os
from collections import namedtuple
import yaml

def get_config():
    with open( os.path.expanduser('~/.mypd.yaml') ) as fh:
        _in = yaml.safe_load(fh)['mypd']
        cls = namedtuple('PDC', tuple(sorted(_in)))
        return cls( **_in )

PDC = get_config()
del os, namedtuple, yaml
