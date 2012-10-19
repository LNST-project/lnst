#! /usr/bin/env python
"""
Software switch

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import getopt
import sys
import logging
import re
import os
from SwSwitch.SwSwitch import SwSwitch
from Common.Logs import Logs

def usage():
    """
    Print usage of this app
    """
    print "Usage: swswitch.py [OPTION...] ACTION"
    print ""
    print "ACTION = [run]"
    print ""
    print "  -d, --debug                             emit debugging messages"
    print "  -h, --help                              print this message"
    print "  -m, --machine-config=FILE               use this machine configuration file"
    print "  -p, --port                              xmlrpc port"
    sys.exit()

def main():
    """
    Main function
    """

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "dhm:p:",
            ["debug", "help", "machine-config=", "port="]
        )
    except getopt.GetoptError as err:
        print str(err)
        usage()
        sys.exit()

    debug = False
    machine_config_path = None
    port = None
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-m", "--machine-config"):
            machine_config_path = arg
        elif opt in ("-p", "--port"):
            port = int(arg)

    Logs(debug, True)
    logging.info("Started")

    if not args:
        logging.error("No action command passed")
        usage();
    action = args[0]

    if not machine_config_path:
        logging.error("No machine config xml file passed")
        usage();
    machine_config_path = os.path.expanduser(machine_config_path)

    handle = open(machine_config_path, "r")
    machine_config_xml = handle.read()
    handle.close()

    if action == "run":
        swswitch = SwSwitch(machine_config_xml, port=port)
        swswitch.run()
    else:
        logging.error("unknown action \"%s\"" % action)
        usage();

if __name__ == "__main__":
    main()
