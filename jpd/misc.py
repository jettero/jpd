#!/usr/bin/env python
# coding: utf-8

import datetime
import shlex
import dateparser

from jpd.config import JPDC
import jpd.const as C


def parse_date(x, in_utc=True, fmt="%Y-%m-%dT%H:%M%Z", utc_to_zulu=True):
    """
    by default we take strings like "now" and "-2d" and translate to the stupid ISO 8601 format
    """

    pd = dateparser.parse(x, settings={"RETURN_AS_TIMEZONE_AWARE": True})
    if in_utc:
        pd = pd.astimezone(datetime.timezone.utc)
    if not fmt:
        return pd
    pd = pd.strftime(fmt)
    return pd[:-3] + "Z" if utc_to_zulu and pd.endswith("UTC") else pd


def aliases_and_colloquialisms(*items, context="user"):
    C.ContextsException.check(context)
    for item in items:
        if isinstance(item, (list, tuple)):
            yield from aliases_and_colloquialisms(*item, context=context)
            continue
        elif isinstance(item, str):
            if item in ("all", "any"):
                if context == 'include':
                    yield from C.INCLUDES
                else:
                    yield None  # None triggers the upper layers to un-fill the param
                break
            elif item in C.SELF_AND_TEAM:
                if context == 'user':
                    yield JPDC.user_id
                    continue
                elif context == 'team':
                    yield from JPDC.team_ids
                    continue
        yield item


def split_strings_maybe(*items, context="user"):
    C.ContextsException.check(context)
    ret = set()
    for item in items:
        if isinstance(item, (list, tuple)):
            r = split_strings_maybe(*item, context=context)
            if r is None:
                break
            ret.update(r)
        elif isinstance(item, str):
            ret.update(shlex.split(item))
    ret = list(sorted(aliases_and_colloquialisms(*ret, context=context)))
    if None in ret:
        return
    if context == "status":
        C.StatusesException.check(*ret, context=context)
    elif context == "include":
        C.IncludesException.check(*ret, context=context)
    return ret
