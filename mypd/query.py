#!/usr/bin/env python
# coding: utf-8

import logging

from pdpyras import APISession as PDSession

from mypd.config import PDC
from mypd.misc import parse_date, split_strings_maybe
from mypd.dq import auto_cache
import mypd.const as C

SESSION = None

log = logging.getLogger("mypd.query")


def get_session():
    global SESSION

    if SESSION is None:
        SESSION = PDSession(PDC.api_key, default_from=PDC.email)

    return SESSION

def fetch_incident(id, sess=get_session(), include=C.INCIDENT_INCLUDES):
    if include := split_strings_maybe(include, context="include"):
        params["include[]"] = statuses
    # XXX: when did I break this... there's nolonger a res=sess.something() at all
    if res.ok:
        return res.json()['incident']

def list_incidents(
    user_ids="me",
    team_ids=None,
    statuses=None,
    since=None,
    until=None,
    sess=get_session(),
    date_range=None,
    test=False,
    include=C.LIST_INCIDENT_INCLUDES,
    **params,
):
    """
    ... need more docs ...
    ... but the below is important enough to mention now

    user_ids[]
    array[string]

    Returns only the incidents currently assigned to the passed user(s). This
    expects one or more user IDs. Note: When using the assigned_to_user filter,
    you will only receive incidents with statuses of triggered or acknowledged.
    This is because resolved incidents are not assigned to any user.
    """
    if user_ids := split_strings_maybe(user_ids, context="user"):
        params["user_ids[]"] = user_ids

    if since is not None:
        params["since"] = parse_date(since)

    if until is not None:
        params["until"] = parse_date(until)

    if team_ids := split_strings_maybe(team_ids):
        params["team_ids[]"] = team_ids

    if statuses := split_strings_maybe(statuses, context="status"):
        params["statuses[]"] = statuses

    if include := split_strings_maybe(include, context="include"):
        params["include[]"] = statuses

    if test:
        return ("/incidents", params)

    log.debug('list_incidents -> list_all(%s)', params)

    return auto_cache(sess.list_all, 'incidents', params=params)
