#!/usr/bin/env python
# coding: utf-8
"""Smoke imports — fails collection if any monitor module has a syntax
error or bad import. Cheap, no fixtures needed."""


def test_imports():
    import jpd.monitor                  # noqa: F401
    import jpd.monitor.app              # noqa: F401
    import jpd.monitor.home             # noqa: F401
    import jpd.monitor.incident         # noqa: F401
    import jpd.monitor.alert            # noqa: F401
    import jpd.monitor.alerts           # noqa: F401
    import jpd.monitor.incidents        # noqa: F401
    import jpd.monitor.modals           # noqa: F401
    import jpd.monitor.actions          # noqa: F401
    import jpd.monitor.config           # noqa: F401
    import jpd.monitor.filters          # noqa: F401
