#!/usr/bin/env python
# coding: utf-8

import hashlib
import os
import simplejson as json
import xdg

XDG_CACHE_LOCATION = os.path.join(xdg.xdg_cache_home(), 'mypd')

def make_key(*a, **kw):
    s = hashlib.sha256()

    for i in a:
        s.update(f'{i}'.encode())

    for k,v in kw.items():
        s.update(f'{k}:{v}'.encode())

    return s.hexdigest()

def cache_json_reply(using_defaults=None, max_age=4000, cache_dir=XDG_CACHE_LOCATION):
    def outer(f):
        def inner(*a, **kw):
            k = make_key(*a, **kw)
            p = os.path.join(cache_dir, k[:4], k[4:] + '.json')
            if os.path.isfile(p):
                with open(p, 'r') as fh:
                    return json.read(fh)
            r = f(*a, **kw)
            with open(p, 'w') as fh:
                json.dump(p, sort_keys=True, indent=2)
            return r
        return inner
    if callable(using_defaults):
        return outer(using_defaults)
    return outer
