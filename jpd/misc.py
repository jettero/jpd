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
    if context == "status":
        C.StatusesException.check(*items)
    elif context == "include":
        C.IncludesException.check(*items)
    for item in items:
        if isinstance(item, (list, tuple)):
            yield from aliases_and_colloquialisms(*item)
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
    ret = set()
    for item in items:
        if isinstance(item, (list, tuple)):
            ret.update(split_strings_maybe(*item))
        elif isinstance(item, str):
            ret.update(shlex.split(item))
    ret = list(sorted(aliases_and_colloquialisms(*ret, context=context)))
    if None in ret:
        return
    return ret