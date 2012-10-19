"""
This module defines Daemon class useful to daemonize process

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import os
import sys

class Daemon:
    def __init__(self, pidfile):
        self._pidfile = pidfile
        self._pid_written = False

    def __del__(self):
        if self._pid_written:
            self._del_pidfile()

    def _read_pid(self):
        try:
            handle = file(self._pidfile, "r")
            pid = int(handle.read().strip())
            handle.close()
        except IOError:
            pid = None
        return pid

    def _write_pid(self, pid):
        handle = file(self._pidfile, "w")
        handle.write("%s\n" % str(pid))
        handle.close()
        self._pid_written = True

    def _del_pidfile(self):
        try:
            os.remove(self._pidfile)
        except OSError as e:
            if e.errno != 2:
                raise(e)

    def _check_pid(self, pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def daemonize(self):
        pid = self._read_pid()
        if pid:
            if self._check_pid(pid):
                logging.error("pidfile in use")
                os.exit(1)
            else:
                self._del_pidfile()
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
            pid = os.getpid()
            self._write_pid(pid)
            logging.info("deamonized with pid %d" % pid)
        except OSError as e:
            logging.error("fork failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)
