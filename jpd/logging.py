#!/usr/bin/env python
# coding: utf-8

import re
import sys
import logging

class KeywordFilter(logging.Filter):
    def __init__(self, *name_filters):
        self.name_filters = [ re.compile(x) for x in name_filters ]

    def filter(self, record):
        for nf in self.name_filters:
            if nf.search( record.name ):
                return True
        return False

def configure_logging(stream=sys.stderr, filename=None, verbosity=0, **kw):
    if filename:
        kw['filename'] = filename
    else:
        kw['stream'] = stream

    main_levels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    kw['level'] = main_levels[max(0, min(verbosity, len(main_levels)-1))]

    logging.root.handlers = []
    logging.basicConfig(**kw)

    kwf = KeywordFilter(r'^jpd$', r'^jpd\.')
    for handler in logging.root.handlers:
        handler.addFilter(kwf)
