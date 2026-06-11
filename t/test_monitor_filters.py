#!/usr/bin/env python
# coding: utf-8

import pytest

from jpd.monitor.config import MonitorConfig
from jpd.monitor.filters import FilterModel, COMPANY_REFUSED


@pytest.fixture
def fresh_config(tmp_path):
    return MonitorConfig(locations=(str(tmp_path / "m.yaml"),))


def test_default_scope_is_mine(fresh_config, monkeypatch):
    monkeypatch.setattr("jpd.monitor.filters.JPDC", _fake_jpdc("Umine", ["TA"]))
    f = FilterModel(fresh_config)
    assert f.scope == "mine"
    kw = f.as_query_kwargs()
    assert kw["user_ids"] == ["Umine"]
    assert kw["team_ids"] is None


def test_team_scope_uses_jpdc_teams(fresh_config, monkeypatch):
    monkeypatch.setattr("jpd.monitor.filters.JPDC", _fake_jpdc("U", ["TA", "TB"]))
    f = FilterModel(fresh_config)
    f.scope = "team"
    kw = f.as_query_kwargs()
    assert kw["user_ids"] is None
    assert kw["team_ids"] == ["TA", "TB"]


def test_custom_with_no_ids_is_refused(fresh_config, monkeypatch):
    monkeypatch.setattr("jpd.monitor.filters.JPDC", _fake_jpdc("U", ["TA"]))
    fresh_config.set("filter", "scope", "custom")
    fresh_config.set("filter", "user_ids", [])
    fresh_config.set("filter", "team_ids", [])
    with pytest.raises(ValueError) as excinfo:
        FilterModel(fresh_config)
    assert "company" in str(excinfo.value).lower()


def test_persist_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("jpd.monitor.filters.JPDC", _fake_jpdc("U", ["TA"]))
    cfg_path = str(tmp_path / "m.yaml")
    mc = MonitorConfig(locations=(cfg_path,))
    f = FilterModel(mc)
    f.scope = "custom"
    f.user_ids = ["U1", "U2"]
    f.team_ids = ["TZ"]
    f.persist_into(mc)
    mc.write()

    mc2 = MonitorConfig(locations=(cfg_path,))
    f2 = FilterModel(mc2)
    assert f2.scope == "custom"
    assert f2.user_ids == ["U1", "U2"]
    assert f2.team_ids == ["TZ"]


class _FakeJPDC:
    def __init__(self, user_id, team_ids):
        self.user_id = user_id
        self.team_ids = tuple(team_ids)


def _fake_jpdc(user_id, team_ids):
    return _FakeJPDC(user_id, team_ids)
