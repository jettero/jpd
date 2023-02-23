#!/usr/bin/env python
# coding: utf-8

import logging
import hashlib
import os
import simplejson as json
import xdg

log = logging.getLogger('mypd.dq')

XDG_CACHE_LOCATION = os.path.join(xdg.xdg_cache_home(), 'mypd')
KEY_SPLIT = 4

def make_key(name, *a, **kw):
    s = hashlib.sha256()

    log.debug('make key for f=%s(a=%s, kw=%s)', name, a, kw)

    for i in a:
        s.update(f'{i}'.encode())

    for k,v in kw.items():
        s.update(f'{k}:{v}'.encode())

    return s.hexdigest()

def auto_cache(f, name, *a, cache_dir=XDG_CACHE_LOCATION, **kw):
    k = make_key(name, *a, **kw) # cache (k)ey
    d = os.path.join(cache_dir, cache_group, k[:KEY_SPLIT]) # (d)ir of cache file
    p = os.path.join(d, k[KEY_SPLIT:] + '.json') # (p)ath of cache file
    s = p[len(cache_dir)+1:] # (s)hort version of the file (sans cache dir)
    if os.path.isfile(p):
        with open(p, 'r') as fh:
            log.debug('returning cache entry %s', s)
            return json.load(fh)
    r = f(*a, **kw) # (r)eturn value
    os.makedirs(d, mode=0o0700, exist_ok=True)
    with open(p, 'w') as fh:
        log.debug('returning cache entry %s', s)
        json.dump(r, fh, sort_keys=True, indent=2)
    return r
