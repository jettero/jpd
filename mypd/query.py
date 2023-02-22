#!/usr/bin/env python
# coding: utf-8

import logging

from pdpyras import APISession as PDSession

from mypd.config import PDC
from mypd.misc import parse_date, split_strings_maybe
from mypd.dq import cache_json_reply
import mypd.const as C

SESSION = None

log = logging.getLogger("mypd.query")


def get_session():
    global SESSION

    if SESSION is None:
        SESSION = PDSession(PDC.api_key, default_from=PDC.email)

    return SESSION

@cache_json_reply
def fetch_incident(id, sess=get_session()):
    res = sess.get(f'/incidents/{id}')
    if res.ok:
        return res.json()['incident']

@cache_json_reply
def list_incidents(
    user_ids="me",
    team_ids=None,
    statuses=None,
    sess=get_session(),
    since=None,
    until=None,
    date_range=None,
    test=False,
    include=C.INCLUDES,
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
        params["since"] = parse_date(since).strftime("%Y-%m-%dT%H:%M%Z")

    if until is not None:
        params["until"] = parse_date(until).strftime("%Y-%m-%dT%H:%M%Z")

    if team_ids := split_strings_maybe(team_ids):
        params["team_ids[]"] = team_ids

    if statuses := split_strings_maybe(statuses, context="status"):
        params["statuses[]"] = statuses

    if include := split_strings_maybe(include, context="include"):
        params["include[]"] = statuses

    log.debug("list_all(params=%s)", params)

    if test:
        return ("/incidents", params)

    return sess.list_all("incidents", params=params)
