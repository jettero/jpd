#!/usr/bin/env python
# coding: utf-8

import datetime
import shlex
import dateparser

from mypd.config import PDC
import mypd.const as C


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
        elif isinstance(item, str):
            if item in ("all", "any"):
                if context == 'include':
                    yield from C.INCLUDES
                    break
                else:
                    yield None  # non triggers the upper layers to un-fill the param
            if context == "status":
                yield item
            elif context == "include":
                yield item
            elif context == "user":
                if item in C.SELF_AND_TEAM:
                    yield PDC.user_id
            elif context == "team":
                if item in C.SELF_AND_TEAM:
                    yield from PDC.team_ids
            else:
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
