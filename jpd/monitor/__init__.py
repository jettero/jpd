def run(_args=None):
    # Lazy import so `jpd.monitor.config` / `jpd.monitor.filters` are
    # importable without textual installed (config + filters carry no TUI deps).
    from jpd.monitor.app import run as _run
    return _run(_args)
