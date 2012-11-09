#! /usr/bin/env python
"""
Switchconfig tool
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import getopt
import sys
import logging
import os
from Switch.SwitchCtl import SwitchCtl
from Common.Logs import Logs

def usage():
    """
    Print usage of this app
    """
    print "Usage: switchconfig.py [OPTION...] ACTION"
    print ""
    print "ACTION = [config | clear | dump]"
    print ""
    print "  -d, --debug                             emit debugging messages"
    print "  -h, --help                              print this message"
    print "  -c, --config=FILE                       use this net configuration file"
    sys.exit()

def main():
    """
    Main function
    """

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "dhc:m:a:",
            ["debug", "help", "config=", "machine-config=", "action="]
        )
    except getopt.GetoptError as err:
        print str(err)
        usage()
        sys.exit()

    debug = False
    config_path = None
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-c", "--config"):
            config_path = arg

    Logs(debug)
    logging.info("Started")

    if not args:
        logging.error("No action command passed")
        usage();
    action = args[0]

    if not config_path:
        logging.error("No switch config file passed")
        usage();
    config_path = os.path.expanduser(config_path)

    handle = open(config_path, "r")
    config_xml = handle.read()
    handle.close()

    switchctl = SwitchCtl(config_xml)
    if action == "config":
        switchctl.init()
        switchctl.configure()
    elif action == "cleanup":
        switchctl.init()
        switchctl.cleanup()
    elif action == "dump":
        from pprint import pprint
        pprint(switchctl.dump_config())
    else:
        logging.error("unknown action \"%s\"" % action)

if __name__ == "__main__":
    main()
