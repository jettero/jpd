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
        status = getattr(e, "status", None) or getattr(getattr(e, "response", None), "status_code", None)
        reason = getattr(e, "message", None) or getattr(getattr(e, "response", None), "reason", None)
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
        status = getattr(e, "status", None) or getattr(getattr(e, "response", None), "status_code", None)
        reason = getattr(e, "message", None) or getattr(getattr(e, "response", None), "reason", None)
        if status == 403:
            log.info("ignoring %d %s for %s", status, reason, query_path)
            return dict()
        raise

    if with_alerts:
        incident["alerts"] = list_alerts(
            incident_id,
            include=[x for x in C.LIST_ALERTS_INCLUDES if x not in "incidents"],
            dry_run=dry_run,
            refresh=refresh,
            sess=sess,
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

    if team_ids := split_strings_maybe(team_ids, context="team"):
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
            incident["alerts"] = list_alerts(incident["id"])
    return incidents


def acknowledge_incident(incident_id=None, sess=None, dry_run=False, refresh=False, **params):
    """Acknowledge a triggered incident and optionally snooze it.

    - If 'snooze' is provided, it may be a duration (e.g., '1h', '3600s', '90m', '1h40s', or integer seconds)
      or an absolute time like '19:00' (today, local time). We translate durations to the
      incidents/{id}/snooze endpoint with 'duration'; for absolute time, we use 'until'.
    - Otherwise we update incident status to 'acknowledged'.
    """
    if sess is None:
        sess = get_session()

    triggered = params.get("triggered")
    snooze = params.get("snooze")

    # Bulk mode: ack all triggered incidents
    if triggered:
        # list current user's triggered incidents
        incidents = list_incidents(statuses=["triggered"], with_alerts=False, sess=sess, dry_run=dry_run, refresh=refresh)
        ids = [inc.get("id") for inc in incidents if inc.get("id")]
        if dry_run:
            return {"bulk_ack_triggered": ids, "snooze": snooze}
        results = []
        for iid in ids:
            results.append(acknowledge_incident(iid, sess=sess, dry_run=False, refresh=refresh, snooze=snooze))
        return results

    query_path = f"incidents/{incident_id}"

    # Single incident path below

    if snooze is not None:
        # parse snooze into either duration seconds or absolute until timestamp
        dur_secs, until_iso = _parse_snooze(snooze)

        snooze_path = f"incidents/{incident_id}/snooze"
        payload = {"snooze": {}}
        if dur_secs is not None:
            payload["snooze"]["duration"] = int(dur_secs)
        if until_iso is not None:
            payload["snooze"]["until"] = until_iso

        if dry_run:
            return (snooze_path, {"method": "POST", "json": payload})

        log.debug("acknowledge_incident -> post(%s)", snooze_path)
        doc = sess.post(snooze_path, json=payload)
        return doc.get("incident", doc)

    # plain acknowledge
    body = {"incident": {"type": "incident", "status": "acknowledged"}}
    if dry_run:
        return (query_path, {"method": "PUT", "json": body})
    log.debug("acknowledge_incident -> put(%s)", query_path)
    doc = sess.put(query_path, json=body)
    return doc.get("incident", doc)


def duration_parse(spec: str) -> int:
    """Parse a duration string into seconds.

    Supports:
    - Integer seconds: "3600"
    - Units: s, m, h, d (e.g., 90m, 1h40s, 2d1h)
    - Kilo-seconds: 4k, 4ks, 4ksec (== 4000)
    Returns seconds (int). If unparsable, defaults to 3600.
    """
    import re

    spec = str(spec).strip()

    # ksec variants: 4k, 4ks, 4ksec
    m = re.fullmatch(r"(\d+)\s*[k](?:\s*s(?:ec)?)?", spec, flags=re.IGNORECASE)
    if m:
        return int(m.group(1)) * 1000

    # Pure integer
    if spec.isdigit():
        return int(spec)

    # Compound duration: (\d+)([smhd]) ...
    total = 0
    matched_any = False
    for qty, unit in re.findall(r"(\d+)\s*([sSmMhHdD])", spec):
        matched_any = True
        n = int(qty)
        u = unit.lower()
        if u == "s":
            total += n
        elif u == "m":
            total += n * 60
        elif u == "h":
            total += n * 3600
        elif u == "d":
            total += n * 86400
    if matched_any:
        return total

    return 3600


def _parse_snooze(spec: str):
    """Parse snooze spec.

    Returns (duration_seconds or None, until_iso or None).
    - Integers => seconds
    - Durations: supports numbers with s/m/h/d (e.g., 3600s, 15m, 1h40s, 2d1h)
    - Clock time HH:MM => absolute time today in local time
    """
    import re
    from datetime import datetime, timedelta

    spec = str(spec).strip()

    # Absolute time HH:MM
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", spec)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        now = datetime.now()
        until = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if until <= now:
            # if time already passed today, choose tomorrow
            until = until + timedelta(days=1)
        return None, until.isoformat(timespec="seconds")

    # Durations via shared parser
    dur = duration_parse(spec)
    if dur is not None:
        return dur, None

    # Fallback: default to 1h
    return 3600, None
