#!/usr/bin/env python
# coding: utf-8

import datetime
import shlex
import dateparser

from .config import PDC

# import datetime
# def host_timezone():
#     return datetime.datetime.now().astimezone().tzinfo


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


def us_and_them(*items, context="user"):
    try:
        context = context.lower()[0]
    except:
        context = 'u'
    if context not in ('u', 't', 's'):
        raise Exception('context must be in (user, team, status)')

    for item in items:
        if isinstance(item, (list, tuple)):
            yield from us_and_them(*item)
        elif isinstance(item, str):
            if item in ("all", "any"):
                yield None # non triggers the upper layers to un-fill the param
                break
            if context =='s':
                if item not in ('triggered', 'resolved', 'acknowledged'):
                    raise Exception("status must be in (triggered, resolved, acknowledged)")
                yield item
            if item in ("me", "mine"):
                yield PDC.user_id
            elif item == "them":
                yield from PDC.team_ids
            elif item == "us":
                if context == 'u':
                    yield PDC.user_id
                elif context == 't':
                    yield PDC.team_ids
            else:
                yield item


def split_strings_maybe(*items, context='user'):
    ret = set()
    for item in items:
        if isinstance(item, (list, tuple)):
            ret.update(split_strings_maybe(*item))
        elif isinstance(item, str):
            ret.update(shlex.split(item))
    ret = list(sorted(us_and_them(*ret, context=context)))
    if None in ret:
        return
    return ret
