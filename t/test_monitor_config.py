#!/usr/bin/env python
# coding: utf-8

import os
import pytest
import yaml

from jpd.monitor.config import MonitorConfig, DEFAULTS


@pytest.fixture
def tmp_config(tmp_path):
    return tmp_path / "jpd.yaml"


def test_defaults_when_missing(tmp_config):
    mc = MonitorConfig(locations=(str(tmp_config),))
    assert mc.get("auto_ack") is False
    assert mc.get("poll_seconds") == 30
    assert mc.get("filter", "scope") == "mine"
    assert mc.get("eos_auto_exit") is True


def test_round_trip_preserves_sibling_keys(tmp_path):
    """The shared ~/.jpd.yaml carries api_key/email/etc.; W must not eat them."""
    p = tmp_path / "jpd.yaml"
    p.write_text("jpd:\n  api_key: secret-shall-not-be-eaten\n  email: x@y\n")

    mc = MonitorConfig(locations=(str(p),))
    mc.set("auto_ack", True)
    mc.set("poll_seconds", 45)
    mc.write()

    reread = yaml.safe_load(p.read_text())
    assert reread["jpd"]["api_key"] == "secret-shall-not-be-eaten"
    assert reread["jpd"]["email"] == "x@y"
    assert reread["jpd"]["monitor"]["auto_ack"] is True
    assert reread["jpd"]["monitor"]["poll_seconds"] == 45


def test_round_trip_when_file_didnt_exist(tmp_config):
    mc = MonitorConfig(locations=(str(tmp_config),))
    mc.set("auto_ack", True)
    mc.set("filter", "scope", "team")
    mc.write()
    assert os.path.isfile(str(tmp_config))

    mc2 = MonitorConfig(locations=(str(tmp_config),))
    assert mc2.get("auto_ack") is True
    assert mc2.get("filter", "scope") == "team"
    # defaults still present for keys we didn't touch
    assert mc2.get("eos_grace_minutes") == 15


def test_partial_block_uses_defaults(tmp_path):
    """Only `auto_ack` set in file — other keys keep code defaults."""
    p = tmp_path / "jpd.yaml"
    p.write_text("jpd:\n  monitor:\n    auto_ack: true\n")
    mc = MonitorConfig(locations=(str(p),))
    assert mc.get("auto_ack") is True
    assert mc.get("poll_seconds") == 30  # default preserved
    assert mc.get("filter", "scope") == "mine"  # default preserved


def test_get_with_default(tmp_config):
    mc = MonitorConfig(locations=(str(tmp_config),))
    assert mc.get("nonexistent", default="x") == "x"
    assert mc.get("filter", "nonexistent", default=[]) == []
