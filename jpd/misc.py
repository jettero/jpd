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
    collected = []
    for item in items:
        if isinstance(item, (list, tuple)):
            collected.extend(aliases_and_colloquialisms(*item, context=context))
            continue
        elif isinstance(item, str):
            if item in ("all", "any"):
                if context == "include":
                    collected.extend(C.INCLUDES)
                else:
                    collected.append(None)  # signals upper layers to omit the param
                break
            elif item in C.SELF_AND_TEAM:
                if context == "user":
                    collected.append(JPDC.user_id)
                    continue
                elif context == "team":
                    collected.extend(JPDC.team_ids)
                    continue
        collected.append(item)

    # Context-specific validation to mirror split_strings_maybe behavior
    if None in collected:
        return collected
    if context == "status":
        C.StatusesException.check(*collected, context=context)
    elif context == "include":
        C.IncludesException.check(*collected, context=context)
    return collected


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
