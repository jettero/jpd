#!/usr/bin/env python
# coding: utf-8

import sys
import argparse
import subprocess
import logging
import simplejson as json

import jpd.query
import jpd.const
import jpd.logging

# log = logging.getLogger("jpd.cmd")


def json_format(args, doc):
    params = dict(sort_keys=True)
    if args.json_indent_level > 0:
        params["indent"] = args.json_indent_level
    else:
        # we take 0 to mean: one line, minified, so we set the separators to
        # have no spaces
        params["separators"] = ",:"
    return json.dumps(doc, **params)


def print_or_whatever(args, doc):
    print(json_format(args, doc))


def _MAP_QUERY(qfunc, *arg_names, **kwarg_mapping):
    """
    gadget for generating standardized-esque jpd.query( +args ) callbacks
    to create a function like this:

        def fetch_incident(args):
            print_or_whatever(json_format( args, jpd.query.fetch_incident(args.incident_id,
                include=args.include, dry_run=args.dry_run, refresh=args.refresh)))

    We can instead write this:

        f = _MAP_QUERY(jpd.query.fetch_incident, 'incident_id', include='')
        # NOTE: to avoid user_ids='user_ids', you can write user_ids='' or user_ids=0 for short
    """

    def inner(args):
        a = tuple(getattr(args, x) for x in arg_names)
        kw = {k: getattr(args, v or k) for k, v in kwarg_mapping.items()}
        kw["dry_run"] = args.dry_run
        kw["refresh"] = args.refresh
        print_or_whatever(args, qfunc(*a, **kw))

    return inner


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
        "-d",
        "--dry-run",
        action="store_true",
        help="invoke the query operation but show the request args rather than executing over HTTP",
    )

    main_parser.add_argument(
        "-S", "--show-parsed-args", action="store_true", help="show the parsed args and options and exit"
    )

    main_parser.add_argument(
        "-j",
        "--json-indent-level",
        type=int,
        default=2,
        help="indent this many spaces in the output json doc, 0 for minified json",
    )

    ############ SETUP CMDS
    subs = main_parser.add_subparsers(required=True, title="Action Commands", metavar="CMD")
    cmd_parsers = list()

    ############ LIST INCIDENTS
    cmd_parsers.append(
        subs.add_parser("list-incidents", aliases=["list", "li", "l"], help='list incidents (aka "PDs")')
    )
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
        "-t",
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
        choices=jpd.const.LIST_INCIDENTS_INCLUDES + ("all",),
        nargs="+",
        metavar="DOCS",
        action="extend",
        help=f"include these sub-documents in the replies, choices: {', '.join(jpd.const.LIST_INCIDENTS_INCLUDES)}",
    )
    cmd_parsers[-1].add_argument(
        "-s",
        "--since",
        "--after",
        type=str,
        help="match incidents on or after this date (examples: yesterday, 72 hours ago, 2023-01-01)",
    )
    cmd_parsers[-1].add_argument(
        "-u",
        "--until",
        "--before",
        type=str,
        help="match incidents on or before this date (examples: yesterday, 72 hours ago, 2023-01-01)",
    )
    cmd_parsers[-1].set_defaults(func=_MAP_QUERY(jpd.query.list_incidents, user_ids="", team_ids="", include=""))

    ############ FETCH INCIDENT
    cmd_parsers.append(
        subs.add_parser(
            "fetch-incident", aliases=["view", "fetch", "v", "f"], help="fetch details about an incident"
        )
    )
    cmd_parsers[-1].add_argument("incident_id", metavar="incident-id", type=str)
    cmd_parsers[-1].add_argument(
        "--without-alerts",
        dest="with_alerts",
        action="store_false",
        help="by default alerts are listed into the output",
    )
    cmd_parsers[-1].add_argument(
        "-i",
        "--include",
        choices=jpd.const.INCIDENT_INCLUDES + ("all",),
        nargs="+",
        metavar="DOCS",
        action="extend",
        help=f"include these sub-documents in the replies, choices: {', '.join(jpd.const.INCIDENT_INCLUDES)}",
    )
    cmd_parsers[-1].set_defaults(func=_MAP_QUERY(jpd.query.fetch_incident, "incident_id", with_alerts='', include=""))

    ############ LIST ALERTS
    cmd_parsers.append(
        subs.add_parser(
            "list-alerts",
            aliases=["lia", "la", "alerts", "a", "fetch-alerts", "fa"],
            help="list the alerts for an incident",
        )
    )
    cmd_parsers[-1].add_argument("incident_id", metavar="incident-id", type=str)
    cmd_parsers[-1].add_argument(
        "-i",
        "--include",
        choices=jpd.const.LIST_ALERTS_INCLUDES + ("all",),
        nargs="+",
        metavar="DOCS",
        action="extend",
        help=f"include these sub-documents in the replies, choices: {', '.join(jpd.const.LIST_ALERTS_INCLUDES)}",
    )
    cmd_parsers[-1].set_defaults(func=_MAP_QUERY(jpd.query.list_alerts, "incident_id", include=""))

    return main_parser, *cmd_parsers
