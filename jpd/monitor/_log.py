"""Debug logging for jpd monitor.

Silent by default. Opt-in via env vars:

  JPD_MONITOR_LOG=/path/to/monitor.log    # write DEBUG-level logs here
  JPD_MONITOR_LOG_LEVEL=INFO              # optional; default DEBUG when log enabled

We log to a file (never stdout/stderr) because the TUI owns the terminal —
printing would corrupt the display. The file is opened in append mode so
multiple runs accumulate; rotate it yourself if you care.

Use:

    from jpd.monitor._log import get_logger
    log = get_logger("app")          # logger name = "jpd.monitor.app"
    log.debug("polling kicked: cadence=%ds", base)

Module-name convention: pass the file's basename (no extension). The hub
logger is "jpd.monitor" so a single handler captures every sub-module.
"""

import logging
import os


_HUB = "jpd.monitor"
_DONE = False


def get_logger(name):
    """Return the logger for `jpd.monitor.<name>`."""
    return logging.getLogger(f"{_HUB}.{name}")


def setup():
    """Wire up the file handler if JPD_MONITOR_LOG is set in the env.

    Idempotent — safe to call multiple times. Reads the env once on first
    call; subsequent calls are no-ops.
    """
    global _DONE
    if _DONE:
        return
    _DONE = True

    log_path = os.environ.get("JPD_MONITOR_LOG")
    if not log_path:
        # Default: no handler attached. The hub logger drops every record
        # because it has no handler and propagate goes to root which also
        # has no handler in our TUI context.
        return

    level_name = (os.environ.get("JPD_MONITOR_LOG_LEVEL") or "DEBUG").upper()
    level = getattr(logging, level_name, logging.DEBUG)

    hub = logging.getLogger(_HUB)
    hub.setLevel(level)
    hub.propagate = False  # don't bubble to root → no stderr noise

    fh = logging.FileHandler(os.path.expanduser(log_path), mode="a")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s.%(msecs)03d  %(name)-26s %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    hub.addHandler(fh)

    hub.info("==== monitor session start (level=%s, path=%s) ====", level_name, log_path)
