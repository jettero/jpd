"""Action dispatchers — thin wrappers so app.py keystrokes don't import query."""

import asyncio

import jpd.query as Q


async def _run(fn, *a, **kw):
    return await asyncio.to_thread(fn, *a, **kw)


async def ack(incident_id):
    return await _run(Q.acknowledge_incident, incident_id)


async def snooze(incident_id, seconds):
    return await _run(Q.acknowledge_incident, incident_id, snooze=int(seconds))


async def merge(parent_id, source_ids):
    return await _run(Q.merge_incidents, parent_id, source_ids)


async def move_alert(alert_id, dest_iid, source_iid):
    return await _run(Q.move_alert, alert_id, dest_iid, source_iid)


async def edit_title(incident_id, title):
    return await _run(Q.update_incident_title, incident_id, title)


async def create_incident(title, service_id):
    return await _run(Q.create_incident, title, service_id)


async def resolve_eos(user_id=None, lookahead_hours=36):
    return await _run(Q.list_my_oncall_until, user_id, lookahead_hours)


async def fetch_incidents(filter_kwargs, refresh=True):
    return await _run(Q.list_incidents, **filter_kwargs, refresh=refresh, with_alerts=True)


async def fetch_notes(incident_id, refresh=True):
    return await _run(Q.list_incident_notes, incident_id, refresh=refresh)
