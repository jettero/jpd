#!/usr/bin/env python
# coding: utf-8

import sys
import jpd.query
import jpd.const
import jpd.logging
import argparse
import logging
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

def fetch_incident(args):
    print(
        json_format( args, jpd.query.fetch_incident(args.incident_id) ) )


def list_incidents(args):
    print(
        json_format(
            args,
            jpd.query.list_incidents(
                user_ids=args.user_ids,
                team_ids=args.team_ids,
                dry_run=args.dry_run,
                include=args.include,
                refresh=args.refresh,
            ),
        )
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


def main(*args):
    main_parser, *other_parsers = arguments_parser()
    args = main_parser.parse_args(*args)

    if args.show_parsed_args:
        doc = dict(**args.__dict__)
        del doc["func"]
        print(json_format(args, doc))
        sys.exit(0)

    jpd.logging.configure_logging(
        verbosity=args.verbose,
    )

    try:
        args.func(args)
    except KeyboardInterrupt:
        pass


entry_point = main


def arguments_parser():
    main_parser = argparse.ArgumentParser(  # description='this program',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    main_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="show various informational things on stderr, more -v, more verbose",
    )
    main_parser.add_argument("-V", "--version", action="store_true", help="show the version and exit")
    main_parser.add_argument("-r", "--refresh", action="store_true", help="refresh query by avoiding disk cache")
    main_parser.add_argument(
        "-S", "--show-parsed-args", action="store_true", help="show the parsed args and options and exit"
    )
    main_parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="invoke the query operation but show the request args rather than executing over HTTP",
    )

    main_parser.add_argument(
        "-j",
        "--json-indent-level",
        type=int,
        default=2,
        help="indent this many spaces in the output json doc, 0 for minified json",
    )

    subs = main_parser.add_subparsers(required=True, title="Action Commands", metavar="CMD")
    cmd_parsers = list()
    cmd_parsers.append(
        subs.add_parser("list-incidents", aliases=["list", "li", "l"], help='list incidents (aka "PDs")')
    )
    cmd_parsers[-1].set_defaults(func=list_incidents)

    cmd_parsers[-1].add_argument(
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

    cmd_parsers[-1].add_argument(
        "-l",
        "--team-ids",
        metavar="team-id",
        type=str,
        nargs="+",
        action="extend",
        help="when listing incidents, show only incidents related to these teams",
    )

    cmd_parsers[-1].add_argument(
        "-i",
        "--include",
        choices=jpd.const.LIST_INCIDENT_INCLUDES + ("all",),
        nargs="+",
        metavar="DOCS",
        action="extend",
        help=f"include these sub-documents in the replies, choices: {', '.join(jpd.const.LIST_INCIDENT_INCLUDES)}",
    )

    cmd_parsers.append(subs.add_parser("fetch-incident", aliases=["view", "fetch", 'v', 'f', "l"], help="fetch details about an incident"))
    cmd_parsers[-1].set_defaults(func=fetch_incident)
    cmd_parsers[-1].add_argument('incident_id', metavar='incident-id', type=str)

    return main_parser, *cmd_parsers
