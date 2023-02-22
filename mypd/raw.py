#!/usr/bin/env python
# coding: utf-8

import logging
import shlex

from pdpyras import APISession as PDSession

from .config import PDC
from .misc import parse_date, us_and_them, split_strings_maybe

SESSION = None

log = logging.getLogger("mypd.raw")


def get_session():
    global SESSION

    if SESSION is None:
        SESSION = PDSession(PDC.api_key, default_from=PDC.email)

    return SESSION


def list_incidents(
    user_ids=None, team_ids=None, statuses=None, sess=get_session(), since=None, until=None, date_range=None, **params
):
    if user_ids is None:
        params["user_ids[]"] = [PDC.user_id]
    elif user_ids := split_strings_maybe(user_ids, context="user"):
        params["user_ids[]"] = user_ids

    if since is not None:
        params["since"] = parse_date(since).strftime("%Y-%m-%dT%H:%M%Z")

    if until is not None:
        params["until"] = parse_date(until).strftime("%Y-%m-%dT%H:%M%Z")

    if team_ids is None:
        params["team_ids[]"] = PDC.team_ids
    elif team_ids := split_strings_maybe(team_ids):
        params["team_ids[]"] = team_ids

    if statuses is None:
        params["statuses[]"] = ["triggered"]
    elif statuses := split_strings_maybe(statuses, context="status"):
        params["statuses[]"] = statuses

    log.debug("list_all(params=%s)", params)

    return sess.list_all("incidents", params=params)
