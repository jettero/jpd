#!/usr/bin/env python
# coding: utf-8

import os
from collections import namedtuple
import yaml
import xdg

# xdg.xdg_config_home() = XDG_CONFIG_HOME = PosixPath('/home/jettero/.config')

DEFAULT_CONFIG_LOCATIONS = (
    os.path.join(xdg.xdg_config_home(), "jpd", "config.yaml"),
    "~/.jpd.yaml",
)

class JPDConfig:
    class Meta:
        fields = ['api_key', 'email', 'user_id', 'team_ids']
        pluralize = { 'team_ids': 'team_id' }
        hide = ['api_key']

    def __init__(self, *locations):
        cls = type(self)
        def gen_prop(field, ufield):
            if field in self.Meta.pluralize:
                setattr(self, ufield, list())
                setattr(cls, field, property(lambda x: tuple(getattr(x, ufield))))
            else:
                setattr(self, ufield, None)
                setattr(cls, field, property(lambda x: getattr(x, ufield)))
        for field in self.Meta.fields:
            ufield = f'_{field}'
            # This gen_prop function only exists to make a pesudo dynamic lexical scope binding
            gen_prop(field, ufield)
        self.locations = DEFAULT_CONFIG_LOCATIONS
        self.read_config(*locations)

    def __repr__(self):
        def hv(f):
            v = getattr(self, f)
            if f in self.Meta.hide:
                return v[:3] + '*' * len(v[3:])
            return v
        vars = ' '.join([ f'{f}={hv(f)}' for f in self.Meta.fields ])
        return f'JPDConfig<{vars}>'

    def read_config(self, *locations):
        read_something = False
        for loc in (locations or self.locations):
            try:
                with open(os.path.expanduser(loc)) as fh:
                    _in = yaml.safe_load(fh)["jpd"]
                    self.grok_config_values(_in)
                    read_something = True
            except FileNotFoundError:
                pass
        if not read_something:
            raise FileNotFoundError(
                f"jpd config not found in any of the known file locations: {', '.join(self.locations)}"
            )

    def grok_config_values(self, _in):
        for field in self.Meta.fields:
            ufield = f'_{field}'
            if non_plural := self.Meta.pluralize.get(field):
                v = _in.get(field, _in.get(non_plural, None))
                a = getattr(self, ufield)
                if v is not None:
                    if isinstance(v, (list,tuple)):
                        a.extend(v)
                    else:
                        a.append(v)
            else:
                setattr(self, ufield, _in.get(field, None))

JPDC = JPDConfig(*DEFAULT_CONFIG_LOCATIONS)
