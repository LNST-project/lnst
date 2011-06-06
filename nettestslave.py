#! /usr/bin/env python
"""
Net test slave

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
from NetTest.NetTestSlave import NetTestSlave
from Common.Daemon import Daemon
from Common.Logs import Logs

def usage():
    """
    Print usage of this app
    """
    print "Usage: nettestslave.py [OPTION...]"
    print ""
    print "  -d, --debug                             emit debugging messages"
    print "  -h, --help                              print this message"
    print "  -e, --daemonize                         go to background after init"
    print "  -i, --pidfile                           file to write daemonized process pid"
    print "  -p, --port                              xmlrpc port"
    sys.exit()

def main():
    """
    Main function
    """
    try:
        opts = getopt.getopt(
            sys.argv[1:],
            "dhei:p:",
            ["debug", "help", "daemonize", "pidfile", "port"]
        )[0]
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit()

    debug = False
    daemon = False
    pidfile = "nettestslave.pid"
    port = None
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-e", "--daemonize"):
            daemon = True
        elif opt in ("-i", "--pidfile"):
            pidfile = arg
        elif opt in ("-p", "--port"):
            port = int(arg)

    Logs(debug, True)
    logging.info("Started")

    if port:
        nettestslave = NetTestSlave(port=port)
    else:
        nettestslave = NetTestSlave()
    if daemon:
        daemon = Daemon(pidfile)
        daemon.daemonize()
    nettestslave.run()

if __name__ == "__main__":
    main()
