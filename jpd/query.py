#!/usr/bin/env python
# coding: utf-8

import logging
from pagerduty import RestApiV2Client, HttpError as PDClientError
import sys
import time

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


_spin_state = {"i": 0}


def _spinner_print(label, done=False):
    # Minimal spinner to stderr; keeps stdout clean for piping.
    frames = ("-", "\\", "|", "/")
    if done:
        # clear line only; no newline to avoid blank lines
        sys.stderr.write("\r\x1b[2K\r")
        sys.stderr.flush()
        return
    i = _spin_state["i"]
    ch = frames[i % len(frames)]
    _spin_state["i"] = i + 1
    # Add two spaces after label to keep cursor off the URL
    sys.stderr.write(f"\r[{ch}] {label}  ")
    sys.stderr.flush()


class Spinner:
    def __init__(self, label):
        self.label = label

    def __enter__(self):
        _spinner_print(self.label)
        return self

    def __exit__(self, exc_type, exc, tb):
        _spinner_print("", done=True)
        return False


def list_incident_notes(incident_id, sess=None, dry_run=False, refresh=False, **params):
    """GET /incidents/{id}/notes — return the chronological list of notes
    attached to an incident. PagerDuty's automation, on-call humans, and
    integrations all write here; the monitor wants to surface them."""
    query_path = f"incidents/{incident_id}/notes"
    if sess is None:
        sess = get_session()
    if dry_run:
        return (query_path, params)
    try:
        with Spinner(f"GET {query_path}"):
            return auto_cache(
                sess.list_all,
                query_path,
                params=params,
                cache_group="list_incident_notes",
                refresh=refresh,
            )
    except PDClientError as e:
        status = getattr(e, "status", None) or getattr(getattr(e, "response", None), "status_code", None)
        if status == 403:
            log.info("ignoring 403 for %s", query_path)
            return list()
        raise


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
        with Spinner(f"GET {query_path}"):
            return auto_cache(
                sess.list_all,
                query_path,
                params=params,
                cache_group="list_alerts",
                refresh=refresh,
            )
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
        # debug log of endpoint
        log.debug("fetch_incident -> get(%s)", query_path)
        with Spinner(f"GET {query_path}"):
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
    with Spinner(f"GET {query_path}"):
        incidents = auto_cache(
            sess.list_all,
            query_path,
            params=params,
            cache_group="list_incidents",
            refresh=refresh,
        )
    if with_alerts:
        for incident in incidents:
            incident["alerts"] = list_alerts(incident["id"])
    return incidents


def list_audit_records(
    since=None,
    until=None,
    root_resource_types=None,
    actions=None,
    actor_id=None,
    actor_type=None,
    sess=None,
    dry_run=False,
    refresh=False,
    **params,
):
    """GET /audit/records — flat list of audit-trail records (who changed what).

    Cursor-based pagination is handled transparently by the client, since
    /audit/records is a registered CURSOR_BASED_PAGINATION_PATHS endpoint; we
    just call list_all and get the unwrapped list back.

    Server-side filters: since/until (ISO8601; omit -> ~last 24h, max ~31d
    span), root_resource_types[] (coarse resource type), actions[]
    (create/update/delete), actor_id, actor_type. The API cannot filter by a
    specific resource id — use filter_audit_records() for that.
    """
    query_path = "audit/records"

    if sess is None:
        sess = get_session()

    if since is not None:
        params["since"] = parse_date(since)

    if until is not None:
        params["until"] = parse_date(until)

    if root_resource_types:
        params["root_resource_types[]"] = list(root_resource_types)

    if actions:
        params["actions[]"] = list(actions)

    if actor_id:
        params["actor_id"] = actor_id

    if actor_type:
        params["actor_type"] = actor_type

    if dry_run:
        return (query_path, params)

    # NOTE: page via iter_cursor, NOT list_all. In pagerduty 6.2.1 iter_all is a
    # generator whose `return self.iter_cursor(...)` for cursor-pagination
    # endpoints terminates the generator empty instead of delegating — so
    # list_all silently returns [] for EVERY cursor endpoint (/audit/records
    # included) and masks HTTP errors as "no records". iter_cursor paginates
    # correctly and raises PDClientError on non-2xx (e.g. a 403 Access Denied,
    # which the audit API returns when the plan/token lacks audit access).
    def _cursor_fetch(path, params=None):
        return list(sess.iter_cursor(path, params=params))

    log.debug("list_audit_records -> iter_cursor(%s, %s)", query_path, params)
    with Spinner(f"GET {query_path}"):
        return auto_cache(
            _cursor_fetch,
            query_path,
            params=params,
            cache_group="list_audit_records",
            refresh=refresh,
        )


def filter_audit_records(records, resource_ids=None, actor_id=None):
    """Client-side post-filter for audit records (the API can't filter by a
    specific resource id).

    Keeps records whose root_resource.id is in resource_ids (when given) AND
    whose actors include actor_id (when given). resource_ids must already be
    concrete ids — the 'mine' keyword is expanded by the caller.
    """
    rid_set = set(resource_ids) if resource_ids else None
    out = []
    for r in records:
        if rid_set is not None and (r.get("root_resource") or {}).get("id") not in rid_set:
            continue
        if actor_id is not None and actor_id not in {(a or {}).get("id") for a in (r.get("actors") or [])}:
            continue
        out.append(r)
    return out


def my_schedule_ids(user_id=None, lookahead_days=90, sess=None, _now=None):
    """GET /oncalls?user_ids[]=<me> over [now, now+lookahead_days]; return the
    sorted distinct schedule ids the user is scheduled to be on-call for going
    forward.

    Forward-looking on purpose: schedules the user has been rotated off of have
    no upcoming on-call entries and correctly drop out. This reflects rotation
    membership within the window, not raw schedule-layer membership — a member
    whose next slot is beyond lookahead_days won't appear until the window
    reaches it. _now is injectable for tests.
    """
    from datetime import datetime, timedelta, timezone
    if sess is None:
        sess = get_session()
    if user_id is None:
        user_id = JPDC.user_id
    now = _now or datetime.now(timezone.utc)

    def _z(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "user_ids[]": [user_id],
        "since": _z(now),
        "until": _z(now + timedelta(days=lookahead_days)),
    }
    with Spinner("GET oncalls"):
        entries = sess.list_all("oncalls", params=params)

    ids = set()
    for e in entries or ():
        sched = e.get("schedule") or {}
        if sched.get("id"):
            ids.add(sched["id"])
    return sorted(ids)


def acknowledge_incident(incident_id=None, sess=None, dry_run=False, refresh=False, triggered=False, **params):
    """Acknowledge a triggered incident and optionally snooze it.

    - If 'snooze' is provided, it may be a duration (e.g., '1h', '3600s', '90m', '1h40s', or integer seconds)
      or an absolute time like '19:00' (today, local time). We translate durations to the
      incidents/{id}/snooze endpoint with 'duration'; for absolute time, we use 'until'.
    - Otherwise we update incident status to 'acknowledged'.
    """
    if sess is None:
        sess = get_session()

    snooze = params.get("snooze")

    # Bulk modes via incident_id keywords or --triggered flag
    # - incident_id == 'all' => all open incidents (triggered + acknowledged)
    # - incident_id == 'triggered' or --triggered => only triggered incidents
    if isinstance(incident_id, str):
        key = incident_id.strip().lower()
        if key in ("all", "triggered") or triggered:
            statuses = None if key == "all" and not triggered else ["triggered"]
            if dry_run:
                path = "incidents"
                return {"bulk": key if key in ("all", "triggered") else "triggered", "path": path, "snooze": snooze}
            incidents = list_incidents(statuses=statuses, with_alerts=False, sess=sess, dry_run=False, refresh=refresh)
            ids = [inc.get("id") for inc in incidents if inc.get("id")]
            results = []
            for iid in ids:
                results.append(acknowledge_incident(iid, sess=sess, dry_run=False, refresh=refresh, snooze=snooze))
            return results

    query_path = f"incidents/{incident_id}"

    # Single incident path below

    if snooze is not None:
        # parse snooze into duration seconds; API only accepts duration
        dur_secs = _parse_snooze(snooze)

        snooze_path = f"incidents/{incident_id}/snooze"
        payload = {"duration": int(dur_secs)}

        if dry_run:
            return (snooze_path, {"method": "POST", "json": payload})

        # Only ACK if needed: fetch current status first
        try:
            with Spinner(f"GET {query_path}"):
                get_resp = sess.get(query_path)
            inc_doc = get_resp.json() if get_resp is not None else {}
        except Exception:
            inc_doc = {}
        current_status = None
        if isinstance(inc_doc, dict):
            inc_obj = inc_doc.get("incident")
            if isinstance(inc_obj, dict):
                current_status = inc_obj.get("status")

        if current_status != "acknowledged":
            ack_body = {"incident": {"type": "incident", "status": "acknowledged"}}
            with Spinner(f"PUT {query_path}"):
                sess.put(query_path, json=ack_body)

        log.debug("acknowledge_incident -> post(%s)", snooze_path)
        with Spinner(f"POST {snooze_path}"):
            resp = sess.post(snooze_path, json=payload)
        try:
            doc = resp.json()
        except Exception:
            doc = {}
        # Prefer incident doc if present; else return minimal success for text mode
        inc = doc.get("incident") if isinstance(doc, dict) else None
        if isinstance(inc, dict) and inc.get("id"):
            return inc
        return {"_ok": True, "_msg": f"[ok] snoozed {incident_id} for {int(dur_secs)}s"}

    # plain acknowledge
    body = {"incident": {"type": "incident", "status": "acknowledged"}}
    if dry_run:
        return (query_path, {"method": "PUT", "json": body})
    log.debug("acknowledge_incident -> put(%s)", query_path)
    with Spinner(f"PUT {query_path}"):
        resp = sess.put(query_path, json=body)
    try:
        doc = resp.json()
    except Exception:
        doc = {}
    inc = doc.get("incident") if isinstance(doc, dict) else None
    if isinstance(inc, dict) and inc.get("id"):
        return inc
    return {"_ok": True, "_msg": f"[ok] acknowledged {incident_id}"}


def resolve_incident(incident_id, sess=None, dry_run=False, **_params):
    """PUT /incidents/{id} — set status=resolved.

    PagerDuty also auto-resolves when every alert under an incident moves
    to resolved, but the human-driven path is to resolve the incident
    itself directly (e.g. after fixing the underlying issue).
    """
    if sess is None:
        sess = get_session()
    query_path = f"incidents/{incident_id}"
    body = {"incident": {"type": "incident", "status": "resolved"}}
    if dry_run:
        return (query_path, {"method": "PUT", "json": body})
    with Spinner(f"PUT {query_path}"):
        resp = sess.put(query_path, json=body)
    try:
        doc = resp.json()
    except Exception:
        doc = {}
    inc = doc.get("incident") if isinstance(doc, dict) else None
    if isinstance(inc, dict) and inc.get("id"):
        return inc
    return {"_ok": True, "_msg": f"[ok] resolved {incident_id}"}


def merge_incidents(parent_id, source_ids, sess=None, dry_run=False, **_params):
    """PUT /incidents/{parent_id}/merge — fold source_ids into parent."""
    if sess is None:
        sess = get_session()
    if isinstance(source_ids, str):
        source_ids = [source_ids]
    source_ids = [s for s in source_ids if s and s != parent_id]
    query_path = f"incidents/{parent_id}/merge"
    body = {"source_incidents": [{"id": s, "type": "incident_reference"} for s in source_ids]}
    if dry_run:
        return (query_path, {"method": "PUT", "json": body})
    with Spinner(f"PUT {query_path}"):
        resp = sess.put(query_path, json=body)
    try:
        doc = resp.json()
    except Exception:
        doc = {}
    inc = doc.get("incident") if isinstance(doc, dict) else None
    if isinstance(inc, dict) and inc.get("id"):
        return inc
    return {"_ok": True, "_msg": f"[ok] merged {len(source_ids)} into {parent_id}"}


def move_alert(alert_id, dest_incident_id, source_incident_id, sess=None, dry_run=False, **_params):
    """PUT /incidents/{dest}/alerts/{alert_id} — reparent alert to dest incident."""
    if sess is None:
        sess = get_session()
    query_path = f"incidents/{dest_incident_id}/alerts/{alert_id}"
    body = {"alert": {"incident": {"id": dest_incident_id, "type": "incident_reference"}}}
    if dry_run:
        return (query_path, {"method": "PUT", "json": body, "source": source_incident_id})
    with Spinner(f"PUT {query_path}"):
        resp = sess.put(query_path, json=body)
    try:
        doc = resp.json()
    except Exception:
        doc = {}
    alert = doc.get("alert") if isinstance(doc, dict) else None
    if isinstance(alert, dict) and alert.get("id"):
        return alert
    return {"_ok": True, "_msg": f"[ok] moved alert {alert_id} -> {dest_incident_id}"}


def update_incident_title(incident_id, title, sess=None, dry_run=False, **_params):
    """PUT /incidents/{id} — set incident title."""
    if sess is None:
        sess = get_session()
    query_path = f"incidents/{incident_id}"
    body = {"incident": {"type": "incident_reference", "title": title}}
    if dry_run:
        return (query_path, {"method": "PUT", "json": body})
    with Spinner(f"PUT {query_path}"):
        resp = sess.put(query_path, json=body)
    try:
        doc = resp.json()
    except Exception:
        doc = {}
    inc = doc.get("incident") if isinstance(doc, dict) else None
    if isinstance(inc, dict) and inc.get("id"):
        return inc
    return {"_ok": True, "_msg": f"[ok] retitled {incident_id}"}


def create_incident(title, service_id, sess=None, dry_run=False, urgency="low", **_params):
    """POST /incidents — create a stub incident under the given service."""
    if sess is None:
        sess = get_session()
    query_path = "incidents"
    body = {
        "incident": {
            "type": "incident",
            "title": title,
            "service": {"id": service_id, "type": "service_reference"},
            "urgency": urgency,
        }
    }
    if dry_run:
        return (query_path, {"method": "POST", "json": body})
    with Spinner(f"POST {query_path}"):
        resp = sess.post(query_path, json=body, headers={"From": JPDC.email or ""})
    try:
        doc = resp.json()
    except Exception:
        doc = {}
    return doc.get("incident") if isinstance(doc, dict) else {"_ok": True, "_msg": "[ok] created"}


def list_my_oncall_until(user_id=None, lookahead_hours=36, sess=None, _now=None):
    """GET /oncalls — return seconds-from-now until the current shift's end.

    Picks the on-call entry whose [start, end) currently contains 'now'; if
    multiple overlap, returns the **earliest** end (next handoff).
    Returns (seconds_until_end, end_iso, schedule_summary) or (None, None, None)
    if no current shift can be resolved within lookahead_hours.

    _now is injectable for tests.
    """
    from datetime import datetime, timedelta, timezone
    if sess is None:
        sess = get_session()
    if user_id is None:
        user_id = JPDC.user_id
    now = _now or datetime.now(timezone.utc)
    until = now + timedelta(hours=lookahead_hours)

    def _z(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "user_ids[]": [user_id],
        "since": _z(now),
        "until": _z(until),
        "earliest": "true",
    }
    query_path = "oncalls"
    with Spinner(f"GET {query_path}"):
        entries = sess.list_all(query_path, params=params)

    best_end = None
    best_summary = None
    for e in entries or ():
        start = _parse_iso(e.get("start"))
        end = _parse_iso(e.get("end"))
        if start is None or end is None:
            continue
        if start <= now < end:
            if best_end is None or end < best_end:
                best_end = end
                sched = e.get("schedule") or {}
                best_summary = sched.get("summary") or sched.get("id")

    if best_end is None:
        return (None, None, None)
    secs = int((best_end - now).total_seconds())
    return (secs, _z(best_end), best_summary)


def _parse_iso(s):
    """Tolerant ISO8601 → tz-aware datetime, or None."""
    from datetime import datetime, timezone
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def duration_parse(spec: str) -> int:
    """Parse a duration string into seconds.

    Supports:
    - Numeric seconds: "3600", "1.5" (fractional ok)
    - Units: s, m, h, d (e.g., 90m, 1h40s, 2d1h, 7.5h — fractional ok)
    - Kilo-seconds: 4k, 4ks, 4ksec (== 4000)
    Returns seconds (int). If unparsable, defaults to 3600.
    """
    import re

    spec = str(spec).strip()

    # ksec variants: 4k, 4ks, 4ksec
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*[k](?:\s*s(?:ec)?)?", spec, flags=re.IGNORECASE)
    if m:
        return int(round(float(m.group(1)) * 1000))

    # Pure number (seconds), possibly fractional
    if re.fullmatch(r"\d+(?:\.\d+)?", spec):
        return int(round(float(spec)))

    # Compound duration: (\d+.\d+)([smhd]) ... — fractional components allowed
    total = 0.0
    matched_any = False
    for qty, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([sSmMhHdD])", spec):
        matched_any = True
        n = float(qty)
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
        return int(round(total))

    return 3600


def _parse_snooze(spec: str):
    """Parse snooze spec.

    Returns duration_seconds (int).
    - Integers => seconds
    - Durations: supports numbers with s/m/h/d (e.g., 3600s, 15m, 1h40s, 2d1h)
    - Clock time => seconds from now() until that local time (tomorrow if past):
        24-hour "HH:MM" (e.g. 21:00) or 12-hour am/pm (e.g. 9pm, 9:30pm, 12am)
    """
    import re
    from datetime import datetime, timedelta

    spec = str(spec).strip()

    def _seconds_until(hh, mm):
        now = datetime.now()
        until = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if until <= now:
            # target already passed today → next occurrence is tomorrow
            until = until + timedelta(days=1)
        return int((until - now).total_seconds())

    # 12-hour am/pm clock: 9pm, 9:30pm, 9 pm, 12am, 12:15AM (dots optional)
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", spec, flags=re.IGNORECASE)
    if m and 1 <= int(m.group(1)) <= 12:
        hh = int(m.group(1)) % 12          # 12 → 0
        mm = int(m.group(2) or 0)
        if mm < 60:
            if m.group(3).lower() == "p":
                hh += 12                    # 12pm → 12, 9pm → 21
            return _seconds_until(hh, mm)

    # 24-hour clock HH:MM
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", spec)
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return _seconds_until(int(m.group(1)), int(m.group(2)))

    # Durations via shared parser
    dur = duration_parse(spec)
    if dur is not None:
        return dur

    # Fallback: default to 1h
    return 3600
