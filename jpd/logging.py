#!/usr/bin/env python
# coding: utf-8

import sys
import logging

class KeywordFilter(logging.Filter):
    def __init__(self, *name_filters):
        self.name_filters = [ re.compile(x) for x in name_filters ]

    def filter(self, record):
        for nf in self.name_filters:
            if nf.search( record.name ):
                return False
        return True

def configure_logging(self, stream=sys.stderr, filename=None, level=logging.ERROR, **kw):
    logging.root.handlers = []
    logging.basicConfig(**kw):
    kwf = KeywordFilter('jpd')
    for handler in logging.root.handlers:
        handler.addFilter(kwf)
