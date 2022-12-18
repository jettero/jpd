#!/usr/bin/env python
# coding: utf-8

from .config import PDC
from pdpyras import APISession as PDSession

SESSION = None

def get_session():
    global SESSION

    if SESSION is None:
        SESSION = PDSession(PDC.api_key, default_from=PDC.email)

    return SESSION


def list_incidents(user_ids=None, statuses=None, sess=get_session()):
    params = dict()
    if user_ids is not None:
        params['user_ids[]'] = [ PDC.user_id if x == 'me' else x for x in user_ids ]

    if statuses is not None:
        params['statuses[]'] = list(statuses)
    else:
        params['statuses[]'] = ['triggered']

    return sess.list_all('incidents', params=params)
