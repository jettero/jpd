#!/usr/bin/env python
# coding: utf-8

import logging
from pagerduty import RestApiV2Client, HttpError as PDClientError

from jpd.config import JPDC
from jpd.misc import parse_date, split_strings_maybe
from jpd.dq import auto_cache
import jpd.const as C

SESSION = None

log = logging.getLogger("jpd.query")


def get_session():
    global SESSION
    if SESSION is None:
        # Initialize the official PagerDuty Rest API v2 client
        SESSION = RestApiV2Client(JPDC.api_key)
    return SESSION


def list_alerts(incident_id, include=C.LIST_ALERTS_INCLUDES, sess=None, dry_run=False, refresh=False, **params):
    query_path = f"incidents/{incident_id}/alerts"

    if sess is None:
        sess = get_session()

    if include := split_strings_maybe(include, context="include"):
        params["include[]"] = include

    if dry_run:
        return (query_path, params)

    log.debug("list_alerts -> list_all(%s, %s)", query_path, params)

    try:
        # RestApiV2Client exposes list_all for collection paths
        return auto_cache(sess.list_all, query_path, params=params, cache_group="list_alerts", refresh=refresh)
    except PDClientError as e:
        status = getattr(e, 'status', None) or getattr(getattr(e, 'response', None), 'status_code', None)
        reason = getattr(e, 'message', None) or getattr(getattr(e, 'response', None), 'reason', None)
        if status == 403:
            # e.response.json()['error'] has further info like "you can't see
            # this" or whatever other useless shit. I just don't think it's
            # worth bothering with
            log.info("ignoring %d %s for %s", status, reason, query_path)
            return list()
        raise

def fetch_incident(
    incident_id, include=C.INCIDENT_INCLUDES, sess=None, dry_run=False, refresh=False, with_alerts=True, **params
):
    query_path = f"incidents/{incident_id}"

    if sess is None:
        sess = get_session()

    if include := split_strings_maybe(include, context="include"):
        params["include[]"] = include

    if dry_run:
        return (query_path, params)

    try:
        # jget equivalent: RestApiV2Client.get returns parsed JSON
        incident = auto_cache(
            sess.get,
            query_path,
            params=params,
            cache_group="fetch_incident",
            refresh=refresh,
            auto_pick="incident",
        )
    except PDClientError as e:
        status = getattr(e, 'status', None) or getattr(getattr(e, 'response', None), 'status_code', None)
        reason = getattr(e, 'message', None) or getattr(getattr(e, 'response', None), 'reason', None)
        if status == 403:
            log.info("ignoring %d %s for %s", status, reason, query_path)
            return dict()
        raise

    if with_alerts:
        incident["alerts"] = list_alerts(
            incident_id, include=[ x for x in C.LIST_ALERTS_INCLUDES if x not in "incidents" ], dry_run=dry_run, refresh=refresh, sess=sess
        )

    return incident


def list_incidents(
    user_ids="me",
    team_ids=None,
    statuses=None,
    since=None,
    until=None,
    include=C.LIST_INCIDENTS_INCLUDES,
    sess=None,
    with_alerts=True,
    dry_run=False,
    refresh=False,
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

    query_path = "incidents"

    if sess is None:
        sess = get_session()

    if user_ids := split_strings_maybe(user_ids, context="user"):
        params["user_ids[]"] = user_ids

    if since is not None:
        params["since"] = parse_date(since)

    if until is not None:
        params["until"] = parse_date(until)

    if team_ids := split_strings_maybe(team_ids, context='team'):
        params["team_ids[]"] = team_ids

    if statuses := split_strings_maybe(statuses, context="status"):
        params["statuses[]"] = statuses

    if include := split_strings_maybe(include, context="include"):
        params["include[]"] = include

    if dry_run:
        return (query_path, params)

    log.debug("list_incidents -> list_all(%s, %s)", query_path, params)

    incidents = auto_cache(sess.list_all, query_path, params=params, cache_group="list_incidents", refresh=refresh)
    if with_alerts:
        for incident in incidents:
            incident['alerts'] = list_alerts(incident['id'])
    return incidents
