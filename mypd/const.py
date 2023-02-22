#!/usr/bin/env python
# coding: utf-8

INCIDENT_INCLUDES = ("field_values",)

LIST_INCIDENT_INCLUDES = (
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

# TODO: I have no interfaces to deal with the fact that includes differ by query type
INCLUDES = INCIDENT_INCLUDES + LIST_INCIDENT_INCLUDES

CONTEXTS = ("user", "team", "status", "include")
STATUSES = ("triggered", "resolved", "acknowledged")

SELF_AND_TEAM = ("me", "mine", "us", "ours")


class StatusesException(Exception):
    SET_MEMBERS = STATUSES
    IMA = "status"

    def __init__(self, moar=None):
        if moar:
            super.__init__(f'{moar} — {self.IMA} must be in ({", ".join(self.SET_MEMBERS)})')
        else:
            super.__init__(f'{self.IMA} must be in ({", ".join(self.SET_MEMBERS)})')

    @classmethod
    def check(cls, *x, fail_raise=True):
        not_in = [y for y in x if y not in cls.SET_MEMBERS]
        if not_in:
            if fail_raise:
                raise cls(f"invalid: {not_in}")
            return False
        return True


class ContextsException(StatusesException):
    SET_MEMBERS = CONTEXTS
    IMA = "context"


class IncludesException(StatusesException):
    SET_MEMBERS = INCLUDES
    IMA = "include"
