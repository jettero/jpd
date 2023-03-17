#!/usr/bin/env python
# coding: utf-8

INCIDENT_INCLUDES = ("field_values",)

LIST_ALERTS_INCLUDES = ("services", "first_trigger_log_entries", "incidents")

LIST_INCIDENTS_INCLUDES = (
    "users",
    "services",
    "first_trigger_log_entries",
    "escalation_policies",
    "teams",
    "assignees",
    "acknowledgers",
    "priorities",
    "conference_bridge",
)

INCLUDES = INCIDENT_INCLUDES + LIST_INCIDENTS_INCLUDES + LIST_ALERTS_INCLUDES

CONTEXTS = ["user", "team"]
STXETNOC = dict()
STATUSES = ("triggered", "resolved", "acknowledged")

SELF_AND_TEAM = ("me", "mine", "us", "ours")

class JPDContextException(Exception):
    SET_MEMBERS = tuple()
    IMA = None

    def __init__(self, moar=None):
        if moar:
            super().__init__(f'{moar} — {self.IMA} must be in ({", ".join(self.SET_MEMBERS)})')
        else:
            super().__init__(f'{self.IMA} must be in ({", ".join(self.SET_MEMBERS)})')

    @classmethod
    def check(cls, *x, fail_raise=True, context=None):
        if context is not None and context in STXETNOC:
            cls = STXETNOC[context]
        not_in = [y for y in x if y not in cls.SET_MEMBERS]
        if not_in:
            if fail_raise:
                raise cls(f"invalid: {not_in}")
            return False
        return True

class StatusesException(JPDContextException):
    SET_MEMBERS = STATUSES
    IMA = "status"

class ContextsException(JPDContextException):
    SET_MEMBERS = CONTEXTS
    IMA = "context"

class IncludesException(JPDContextException):
    SET_MEMBERS = INCLUDES
    IMA = "include"

class IncidentIncludesException(IncludesException):
    SET_MEMBERS = INCIDENT_INCLUDES
    IMA = "incident-include"

class ListIncidentIncludesException(IncludesException):
    SET_MEMBERS = INCIDENT_INCLUDES
    IMA = "list-incident-include"

# meta class bullshit

for item in dir():
    try:
        if item.endswith('Exception'):
            item = globals()[item]
            if issubclass(item, JPDContextException):
                if item.IMA is not None and item.IMA not in CONTEXTS:
                    CONTEXTS.append(item.IMA)
                    STXETNOC[item.IMA] = item
    except TypeError:
        pass

CONTEXTS = tuple(CONTEXTS)
