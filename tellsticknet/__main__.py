#!/usr/bin/env python3

import logging
import re
from datetime import datetime
from sys import argv, stdout, stderr, stdin

from tellsticknet.protocol import decode_packet
from tellsticknet.controller import discover

from json import dumps as to_json

LOGFMT = "%(asctime)s %(levelname)5s (%(threadName)s) [%(name)s]  %(message)s"
DATEFMT = "%y-%m-%d %H:%M.%S"
LOG_LEVEL = logging.INFO
_LOGGER = logging.getLogger(__name__)

try:
    import coloredlogs
    coloredlogs.install(level=LOG_LEVEL)
except:
    _LOGGER.debug("no color log")

logging.basicConfig(level=LOG_LEVEL,
                    stream=stderr,
                    datefmt=DATEFMT,
                    format=LOGFMT)


def parse_isoformat(s):
    """Parse string with date in ISO 8601 format as datetime

    >>> parse_isoformat("2016-01-15T11:39:15")
    datetime.datetime(2016, 1, 15, 11, 39, 15)
    """
    return datetime(*map(int, re.split("[-:T]", s)))


def parse_stdin():
    """Parse protocol data passed on stdin, previously captured

    example to print all captured sensor id:s
    cat /tmp/packets.txt  | ./script/parse | jq ".sensorId" | sort | uniq
    """
    for line in stdin.readlines():
        line = line.strip()
        if " " in line:
            # assume we have date + raw data
            timestamp, line = line.split()
            timestamp = int(parse_isoformat(timestamp).timestamp())
            print(to_json(decode_packet(line, lastUpdated=timestamp)))
        else:
            print(to_json(decode_packet(line)))


def prepend_timestamp(line):
    """Add ISO 8601 timestamp to line"""
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    return "{} {}".format(timestamp, line)


def print_event_stream():
    """Print event stream"""
    controllers = discover()

    # for now only care about one controller
    controller = next(controllers, None)
    if controller is None:
        print("no tellstick devices found")
        exit(0)

    if argv[-1] == "raw":
        stream = map(prepend_timestamp, controller.packets())
    else:
        stream = controller.values()

    for packet in stream:
        print(packet)
        try:
            stdout.flush()
        except IOError:
            # broken pipe
            pass


if __name__ == "__main__":
    if argv[-1] == "mock":
        from tellsticknet.discovery import mock
        mock()
    elif not stdin.isatty():
        parse_stdin()
    else:
        print_event_stream()
