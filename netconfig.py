#! /usr/bin/env python
"""
Netconfig tool

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
from pprint import pprint
from NetConfig.NetConfig import NetConfig
from NetConfig.NetConfigParse import NetConfigParse
from NetConfig.NetConfigDevice import NetConfigDeviceAllCleanup
from Common.Logs import Logs

def usage():
    """
    Print usage of this app
    """
    print "Usage: netconfig.py [OPTION...] ACTION"
    print ""
    print "ACTION = [up | down | dump | cleanup | test]"
    print ""
    print "  -d, --debug                             emit debugging messages"
    print "  -h, --help                              print this message"
    print "  -c, --config=FILE                       use this net configuration file"
    print "  -m, --machine-config=FILE               use this machine configuration file"
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
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit()

    debug = False
    config_path = None
    machine_config_path = None
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-c", "--config"):
            config_path = arg
        elif opt in ("-m", "--machine-config"):
            machine_config_path = arg

    Logs(debug)
    logging.info("Started")

    if not args:
        logging.error("No action command passed")
        usage();

    action = args[0]
    if action == "cleanup":
        NetConfigDeviceAllCleanup()
        return

    if not machine_config_path:
        logging.error("No machine config xml file passed")
        usage();
    machine_config_path = os.path.expanduser(machine_config_path)

    handle = open(machine_config_path, "r")
    machine_config_xml = handle.read()
    handle.close()

    if action == "refresh":
        logging.info("Refreshing machine config")
        net_config_parse = NetConfigParse(machine_config_xml)
        output = net_config_parse.refresh_machine_config()
        handle = open(machine_config_path, "w")
        handle.write(output)
        handle.close()
        return

    if not config_path:
        logging.error("No net config file/dir passed")
        usage();
    config_path = os.path.expanduser(config_path)

    if action == "test":
        '''
        Go through specified directory and use all xmls and configs
        '''

        for root, dirs, files in os.walk(config_path):
            for f in files:
                config_file = os.path.join(config_path, f)
                if not re.match(r'^.*\.xml$', config_file):
                    continue
                handle = open(config_file, "r")
                config_xml = handle.read()
                handle.close()
                logging.info("Processing config file \"%s\"" % config_file)
                net_config = NetConfig(machine_config_xml, config_xml)
                net_config.configure_all()
                net_config.deconfigure_all()
        return

    handle = open(config_path, "r")
    config_xml = handle.read()
    handle.close()

    net_config = NetConfig(machine_config_xml, config_xml)
    if action == "up":
        net_config.configure_all()
    elif action == "down":
        net_config.deconfigure_all()
    elif action == "dump":
        pprint(net_config.dump_config())
    else:
        logging.error("unknown action \"%s\"" % action)

if __name__ == "__main__":
    main()
