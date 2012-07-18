#! /usr/bin/env python
"""
Net test controller

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
import os
import re
from NetTest.NetTestController import NetTestController
from NetTest.NetTestResultSerializer import NetTestResultSerializer
from Common.Logs import Logs
from Common.LoggingServer import LoggingServer
import Common.ProcessManager

def usage():
    """
    Print usage of this app
    """
    print "Usage:"
    print "nettestctl.py [OPTION...] ACTION"
    print ""
    print "ACTION = [run | dump | config_only]"
    print ""
    print "  -d, --debug                             emit debugging messages"
    print "  -p, --packet_capture                    capture and log all ongoing\n" \
          "                                          network communication during\n" \
          "                                          the test"
    print "  -h, --help                              print this message"
    print "  -r, --recipe=FILE                       use this net test recipe"
    print "  -e, --remoteexec                        transfer and execute\n" \
          "                                          application on slaves"
    print "  -c, --cleanup                           perform config cleanup\n" \
          "                                          machines"
    print "  -x, --result=FILE                       file to write xml_result"
    sys.exit()

def process_recipe(args, file_path, remoteexec, cleanup,
                   res_serializer, packet_capture):
    nettestctl = NetTestController(os.path.realpath(file_path),
                                   remoteexec=remoteexec, cleanup=cleanup,
                                   res_serializer=res_serializer)
    action = args[0]
    if action == "run":
        return nettestctl.run_recipe(packet_capture)
    elif action == "dump":
        return nettestctl.dump_recipe()
    elif action == "config_only":
        return nettestctl.config_only_recipe()
    else:
        logging.error("Unknown action \"%s\"" % action)
        usage();

def print_summary(summary):
    logging.info("====================== SUMMARY ======================")
    for recipe_file, res in summary:
        if res:
            res = "PASS"
        else:
            res = "FAIL"
        logging.info("*%s* %s" % (res, recipe_file))
    logging.info("=====================================================")

def get_recipe_result(args, file_path, remoteexec, cleanup,
                      res_serializer, packet_capture):
    res_serializer.add_recipe(file_path)
    Logs.set_logging_root_path(file_path)
    loggingServer = LoggingServer(LoggingServer.DEFAULT_PORT,
                                  Logs.root_path, Logs.debug)
    loggingServer.start()
    res = process_recipe(args, file_path, remoteexec, cleanup,
                         res_serializer, packet_capture)
    loggingServer.stop()
    return ((file_path, res))

def main():
    """
    Main function
    """
    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "dhr:ecx:p",
            ["debug", "help", "recipe=", "remoteexec", "cleanup", "result=",
             "packet_capture"]
        )
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit()

    debug = 0
    recipe_path = None
    remoteexec = False
    cleanup = False
    result_path = None
    packet_capture = False
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug += 1
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-r", "--recipe"):
            recipe_path = arg
        elif opt in ("-e", "--remoteexec"):
            remoteexec = True
        elif opt in ("-c", "--cleanup"):
            cleanup = True
        elif opt in ("-x", "--result"):
            result_path = arg
        elif opt in ("-p", "--packet_capture"):
            packet_capture = True


    Logs(debug)

    if not args:
        logging.error("No action command passed")
        usage();

    if not recipe_path:
        logging.error("No recipe xml file passed")
        usage();

    summary = []

    res_serializer = NetTestResultSerializer()
    if os.path.isdir(recipe_path):
        all_files = []
        for root, dirs, files in os.walk(recipe_path):
            dirs[:] = [] # do not walk subdirs
            all_files += files

        all_files.sort()
        for f in all_files:
            recipe_file = os.path.join(recipe_path, f)
            if re.match(r'^.*\.xml$', recipe_file):
                logging.info("Processing recipe file \"%s\"" % recipe_file)
                summary.append(get_recipe_result(args, recipe_file, remoteexec,
                                                 cleanup, res_serializer,
                                                 packet_capture))
                Logs.set_logging_root_path(clean=False)
    else:
        summary.append(get_recipe_result(args, recipe_path, remoteexec,
                                         cleanup, res_serializer,
                                         packet_capture))
    Logs.set_logging_root_path(clean=False)

    print_summary(summary)

    if result_path:
        result_path = os.path.expanduser(result_path)
        handle = open(result_path, "w")
        handle.write(str(res_serializer))
        handle.close()

if __name__ == "__main__":
    main()
