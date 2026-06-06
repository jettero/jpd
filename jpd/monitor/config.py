"""MonitorConfig — settings under `jpd.monitor:` in the shared jpd config
file (~/.jpd.yaml, or the XDG path). Reads from the same locations as
`JPDConfig`; writes are read-modify-write so sibling keys (api_key, email,
user_id, team_ids) are preserved.

Cost we accept: PyYAML doesn't preserve comments on safe_dump, so pressing
`W` will reformat the file. If you keep important comments in
`~/.jpd.yaml`, prefer hand-editing the `jpd.monitor:` block over `W`.
"""

import os
import yaml

from jpd.config import DEFAULT_CONFIG_LOCATIONS


DEFAULTS = {
    "auto_ack": False,
    "poll_seconds": 30,
    "eos_auto_exit": True,
    "eos_grace_minutes": 15,
    "eos_override": None,
    "eos_lookahead_hours": 36,
    "filter": {
        "scope": "mine",
        "user_ids": [],
        "team_ids": [],
        "statuses": ["triggered", "acknowledged"],
    },
    # Show service-summary prefix on each row (same toggle as `jpd li`).
    "show_service_info": False,
}


class MonitorConfig:
    def __init__(self, locations=None):
        self.locations = locations or DEFAULT_CONFIG_LOCATIONS
        self.data = _deep_copy(DEFAULTS)
        self.write_path = os.path.expanduser(self.locations[0])
        self._read()

    def _read(self):
        for loc in self.locations:
            path = os.path.expanduser(loc)
            if not os.path.isfile(path):
                continue
            with open(path) as fh:
                doc = yaml.safe_load(fh) or {}
            if not isinstance(doc, dict):
                continue
            mon = (doc.get("jpd") or {}).get("monitor") or {}
            if isinstance(mon, dict):
                _deep_merge(self.data, mon)
            # Write back to wherever we read from (preserve user's choice
            # of XDG vs ~/.jpd.yaml).
            self.write_path = path
            break

    def write(self):
        """Read-modify-write so we don't clobber sibling keys like
        api_key/email/user_id that JPDConfig owns."""
        path = self.write_path
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        doc = {}
        if os.path.isfile(path):
            with open(path) as fh:
                doc = yaml.safe_load(fh) or {}
        if not isinstance(doc, dict):
            doc = {}
        jpd_obj = doc.get("jpd")
        if not isinstance(jpd_obj, dict):
            jpd_obj = {}
            doc["jpd"] = jpd_obj
        jpd_obj["monitor"] = _deep_copy(self.data)
        with open(path, "w") as fh:
            yaml.safe_dump(doc, fh, default_flow_style=False, sort_keys=True)

    def get(self, *keys, default=None):
        cur = self.data
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def set(self, *keys_and_value):
        *keys, value = keys_and_value
        cur = self.data
        for k in keys[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value


def _deep_copy(x):
    if isinstance(x, dict):
        return {k: _deep_copy(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_deep_copy(v) for v in x]
    return x


def _deep_merge(dst, src):
    if not isinstance(src, dict):
        return
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = _deep_copy(v)
