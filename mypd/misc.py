#!/usr/bin/env python
# coding: utf-8

import datetime
import dateparser

# import datetime
# def host_timezone():
#     return datetime.datetime.now().astimezone().tzinfo

def parse_date(x, in_utc=True, fmt='%Y-%m-%dT%H:%M%Z', utc_to_zulu=True):
    """
    by default we take strings like "now" and "-2d" and translate to the stupid ISO 8601 format
    """

    pd = dateparser.parse(x, settings={'RETURN_AS_TIMEZONE_AWARE': True})
    if in_utc:
        pd = pd.astimezone(datetime.timezone.utc)
    if not fmt:
        return pd
    pd = pd.strftime(fmt)
    return pd[:-3] + 'Z' if utc_to_zulu and pd.endswith('UTC') else pd

