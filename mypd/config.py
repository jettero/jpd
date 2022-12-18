#!/usr/bin/env python
# coding: utf-8

import os
from collections import namedtuple
import yaml

DEFAULT_CONFIG_LOCATION = [
    '~/.config/mypd/config.yaml',
    '~/.mypd.yaml',
]

def get_config(loc=None):
    if loc is None:
        e = list()
        for thing in DEFAULT_CONFIG_LOCATION:
            try:
                return get_config(thing)
            except FileNotFoundError as _e:
                e.append(_e)
        raise FileNotFoundError(f"mypd config not found in any of the default locations: {', '.join(DEFAULT_CONFIG_LOCATION)}")

    with open( os.path.expanduser(loc) ) as fh:
        _in = yaml.safe_load(fh)['mypd']
        cls = namedtuple('PDC', tuple(sorted(_in)))
        return cls( **_in )

def reload_config(loc=None):
    global PDC
    try:
        PDC = get_config(loc=loc)
    except:
        PDC = None

reload_config()
