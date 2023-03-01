#!/usr/bin/env python
# coding: utf-8

import logging
import hashlib
import datetime
import os
import simplejson as json
import xdg

log = logging.getLogger("jpd.dq")

XDG_CACHE_LOCATION = os.path.join(xdg.xdg_cache_home(), "jpd")
KEY_SPLIT = 4


def min_dump(x):
    # NOTE: we want this to crash if one of the args is an obj
    #
    # In [3]: import simplejson as json
    #    ...: json.dumps({'one': [ ['thing', 'leads'], ['to', 'another'] ], 'two': 2, 'aaa': 3, 'zzz': 4}, sort_keys=True, ensure_ascii=True, indent=None, separators=',:')
    # Out[3]: '{"aaa":3,"one":[["thing","leads"],["to","another"]],"two":2,"zzz":4}'
    #
    return json.dumps(x, sort_keys=True, ensure_ascii=True, indent=None, separators=",:")


def make_key(name, *a, **kw):
    s = hashlib.sha256()

    log.debug("make key for f=%s(a=%s, kw=%s)", name, a, kw)

    s.update(name.encode())
    s.update(min_dump(a).encode())
    s.update(min_dump(kw).encode())

    return s.hexdigest()


def clean_cache(cache_dir=XDG_CACHE_LOCATION, cache_group=None, max_age=300):
    now = datetime.datetime.now().timestamp()
    top = cache_dir
    log.debug(f'cache_clean: top={top}')
    if cache_group is not None:
        top = os.path.join(top, cache_group)
    for path, _, files in os.walk(top):
        count = len(files)
        log.debug(f'  path={path}')
        for file in files:
            fpath = os.path.join(path, file)
            δt = int(now - os.stat(fpath).st_mtime)
            OLD = δt > max_age
            if OLD:
                try:
                    os.unlink(fpath)
                    log.debug("    unlink(fpath=%s)", fpath)
                    count -= 1
                except (OSError, PermissionError) as e:
                    log.debug("    unlink(fpath=%s):", fpath)
                    log.debug("      %s", e)
        if count < 1:
            try:
                os.removedirs(path)
                log.debug("    removedirs(path=%s)", path)
            except (OSError, PermissionError) as e:
                log.debug("    removedirs(path=%s):", path)
                log.debug("      %s", e)

def auto_cache(f, *a, cache_dir=XDG_CACHE_LOCATION, cache_group=None, refresh=False, **kw):
    # we could optionally clean the cache one query at a time...
    #   clean_cache(cache_dir=cache_dir, cache_group=cache_group)
    clean_cache(cache_dir=cache_dir) # but why??

    if cache_group is None:
        cache_group = f.__name__
    k = make_key(cache_group, *a, **kw)  # cache (k)ey
    d = os.path.join(cache_dir, cache_group, k[:KEY_SPLIT])  # (d)ir of cache file
    p = os.path.join(d, k[KEY_SPLIT:] + ".json")  # (p)ath of cache file
    s = p[len(cache_dir) + 1 :]  # (s)hort version of the file (sans cache dir)
    if os.path.isfile(p) and not refresh:
        with open(p, "r") as fh:
            log.debug("returning cache entry %s", s)
            return json.load(fh)
    r = f(*a, **kw)  # (r)eturn value
    os.makedirs(d, mode=0o0700, exist_ok=True)
    with open(p, "w") as fh:
        log.debug("returning cache entry %s", s)
        json.dump(r, fh, sort_keys=True, indent=2)
    return r
