#!/usr/bin/env python
# coding: utf-8

import datetime
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
    for item in items:
        if isinstance(item, (list, tuple)):
            yield from _us_and_them(*item)
        elif isinstance(item, str):
            if item in ("all", "any"):
                if context == "status":
                    yield from ("triggered", "acknowledged", "resolved")
            if item in ("me", "mine"):
                yield PDC.user_id
            elif item == "them":
                yield from PDC.team_ids
            elif item == "us":
                if context == "user":
                    yield PDC.user_id
                elif context == "teams":
                    yield PDC.team_ids


def split_strings_maybe(*items):
    ret = set()
    for item in items:
        if isinstance(item, (list, tuple)):
            ret.update(_split_strings_maybe(*item))
        elif isinstance(item, str):
            ret.add(_us_and_them(*shlex.split(item)))
    return list(sorted(ret))
