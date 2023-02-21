#!/usr/bin/env python
# coding: utf-8

import logging
from .config import PDC
from .misc import parse_date
from pdpyras import APISession as PDSession

SESSION = None

log = logging.getLogger("mypd.raw")


def get_session():
    global SESSION

    if SESSION is None:
        SESSION = PDSession(PDC.api_key, default_from=PDC.email)

    return SESSION

def list_incidents(user_ids=None, team_ids=None, statuses=None, sess=get_session(), since=None, until=None, date_range=None, **params):
    if user_ids is not None:
        params["user_ids[]"] = [PDC.user_id if x in ("me", "us", "mine") else x for x in user_ids]

    if since is not None:
        params['since'] = parse_date(since).strftime('%Y-%m-%dT%H:%M%Z')

    if until is not None:
        params['until'] = parse_date(until).strftime('%Y-%m-%dT%H:%M%Z')

    if team_ids is not None:
        teams = list()
        for item in team_ids:
            if item in ("me", "us", "mine"):
                teams.extend(PDC.team_ids)
            else:
                teams.append(item)
        params["team_ids[]"] = teams

    if statuses is not None:
        params["statuses[]"] = list(statuses)
    else:
        params["statuses[]"] = ["triggered"]

    log.debug("list_all(params=%s)", params)

    return sess.list_all("incidents", params=params)
