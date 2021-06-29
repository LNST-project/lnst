#! /usr/bin/env python3
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
import os
import logging
from lnst.Common.Daemon import Daemon
from lnst.Common.Logs import LoggingCtl
from lnst.Common.Colours import load_presets_from_config
from lnst.Slave.Config import SlaveConfig
from lnst.Slave.NetTestSlave import NetTestSlave

def usage():
    """
    Print usage of this app
    """
    print("Usage: %s [OPTION...]" % sys.argv[0])
    print("")
    print("  -d, --debug                emit debugging messages")
    print("  -h, --help                 print this message")
    print("  -e, --daemonize            go to background after init")
    print("  -i, --pidfile              file to write daemonized process pid")
    print("  -m, --no-colours           disable coloured terminal output")
    print("  -p, --port                 xmlrpc port to listen on")
    sys.exit()

def main():
    """
    Main function
    """
    try:
        opts = getopt.getopt(
            sys.argv[1:],
            "dhei:p:m",
            ["debug", "help", "daemonize", "pidfile=", "port=", "no-colours"]
        )[0]
    except getopt.GetoptError as err:
        print(str(err))
        usage()
        sys.exit()

    slave_config = SlaveConfig()
    dirname = os.path.dirname(sys.argv[0])

    git_cfg = os.path.join(dirname, "lnst-slave.conf")
    user_cfg = os.path.expanduser('~/.lnst/lnst-slave.conf')
    if os.path.isfile(git_cfg):
        slave_config.load_config(git_cfg)
    elif os.path.isfile(user_cfg):
        slave_config.load_config(user_cfg)
    else:
        slave_config.load_config("/dev/null")



    debug = False
    daemon = False
    pidfile = "/var/run/lnst-slave.pid"
    port = None
    coloured_output = not slave_config.get_option("colours", "disable_colours")
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
        elif opt in ("-m", "--no-colours"):
            coloured_output = False

    load_presets_from_config(slave_config)

    log_ctl = LoggingCtl(debug,
                     log_dir=slave_config.get_option('environment', 'log_dir'),
                     colours=coloured_output)
    logging.info("Started")

    if port != None:
        slave_config.set_option("environment", "rpcport", port)

    nettestslave = NetTestSlave(log_ctl, slave_config)

    if daemon:
        daemon = Daemon(pidfile)
        daemon.daemonize()
    nettestslave.run()

if __name__ == "__main__":
    main()
