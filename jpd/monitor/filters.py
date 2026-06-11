from jpd.config import JPDC


SCOPES = ("mine", "team", "custom")
COMPANY_REFUSED = "all-of-company scope is not supported in jpd monitor"


class FilterModel:
    """Resolves filter scope + custom lists into list_incidents() kwargs."""

    def __init__(self, mon_cfg):
        self.mon = mon_cfg
        f = mon_cfg.get("filter", default={}) or {}
        self.scope = f.get("scope") or "mine"
        self.user_ids = list(f.get("user_ids") or [])
        self.team_ids = list(f.get("team_ids") or [])
        self.statuses = list(f.get("statuses") or ["triggered", "acknowledged"])
        self._validate()

    def _validate(self):
        if self.scope not in SCOPES:
            self.scope = "mine"
        if self.scope == "custom" and not self.user_ids and not self.team_ids:
            raise ValueError(COMPANY_REFUSED)

    def as_query_kwargs(self):
        """Return the kwargs to pass to jpd.query.list_incidents()."""
        if self.scope == "mine":
            return {"user_ids": [JPDC.user_id], "team_ids": None, "statuses": self.statuses}
        if self.scope == "team":
            tids = list(JPDC.team_ids) or list(self.team_ids)
            if not tids:
                raise ValueError("team scope but no team_ids configured")
            return {"user_ids": None, "team_ids": tids, "statuses": self.statuses}
        return {
            "user_ids": list(self.user_ids) or None,
            "team_ids": list(self.team_ids) or None,
            "statuses": self.statuses,
        }

    def description(self):
        if self.scope == "mine":
            return f"mine ({JPDC.user_id})"
        if self.scope == "team":
            tids = list(JPDC.team_ids) or list(self.team_ids)
            return f"team ({', '.join(tids)})"
        bits = []
        if self.user_ids:
            bits.append("u=" + ",".join(self.user_ids))
        if self.team_ids:
            bits.append("t=" + ",".join(self.team_ids))
        return "custom (" + " ".join(bits) + ")"

    def persist_into(self, mon_cfg):
        mon_cfg.set("filter", "scope", self.scope)
        mon_cfg.set("filter", "user_ids", list(self.user_ids))
        mon_cfg.set("filter", "team_ids", list(self.team_ids))
        mon_cfg.set("filter", "statuses", list(self.statuses))
