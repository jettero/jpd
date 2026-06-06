#!/usr/bin/env python

# Force the script's directory ahead of site-packages so the dev tree
# always wins over a stale `pip install .` snapshot. Without this, a
# previous `pip install .` leaves an older `jpd` in site-packages that
# gets imported instead of the working copy.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import jpd.cmd
jpd.cmd.entry_point()
