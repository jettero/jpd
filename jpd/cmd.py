#!/usr/bin/env python
# coding: utf-8

import sys
from jpd import list_incidents
import jpd.const as C
import argparse
import simplejson as json


def json_format(args, doc):
    params = dict(sort_keys=True)
    if args.json_indent_level > 0:
        params["indent"] = args.json_indent_level
    else:
        # we take 0 to mean: one line, minified, so we set the separators to
        # have no spaces
        params["separators"] = ",:"
    return json.dumps(doc, **params)


def main(args):
    doc = list_incidents(user_ids=args.user_ids, team_ids=args.team_ids, dry_run=args.dry_run, include=args.include)
    print(json_format(args, doc))


def entry_point(*args):
    parser = argparse.ArgumentParser(  # description='this program',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show various informational things on stderr")
    parser.add_argument("-V", "--version", action="store_true", help="show the version and exit")
    parser.add_argument("--show-parsed-args", action="store_true", help="show the parsed args and options and exit")
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="invoke the query operation but show the request args rather than executing over HTTP",
    )

    parser.add_argument(
        "-j",
        "--json-indent-level",
        type=int,
        default=2,
        help="indent this many spaces in the output json doc, 0 for minified json",
    )

    class MyReplaceDefaultExtend(argparse._ExtendAction):
        def __init__(self, *a, **kw):
            self.first_time = True
            super().__init__(*a, **kw)

        def __call__(self, parser, namespace, *a, **kw):
            if self.first_time:
                setattr(namespace, self.dest, list())
                self.first_time = False
            super().__call__(parser, namespace, *a, **kw)

    class formatted_list(list):
        def __repr__(self):
            return ", ".join(self)

    parser.add_argument(
        "-u",
        "--user-ids",
        metavar="user-id",
        type=str,
        nargs="*",
        action=MyReplaceDefaultExtend,
        default=formatted_list(("mine",)),
        help="when listing incidents, only show incidents assigned to these users"
        " - note that -u with no args will clear the default",
    )

    parser.add_argument(
        "-l",
        "--team-ids",
        metavar="team-id",
        type=str,
        nargs="+",
        action="extend",
        help="when listing incidents, show only incidents related to these teams",
    )

    parser.add_argument(
        "-i",
        "--include",
        choices=C.INCLUDES + ("all",),
        nargs="+",
        action="extend",
        help="include these sub-documents in the replies",
    )

    args = parser.parse_args(*args)

    if args.show_parsed_args:
        print(args)
        sys.exit(0)

    try:
        main(args)
    except KeyboardInterrupt:
        pass
