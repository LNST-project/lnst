"""
This module contains tools for capturing packets within LNST.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import subprocess

class PacketCapture:
    """ Capture/handle traffic that goes through a specific
        network interface. Capturing backend of this class
        is provided by tcpdump(8).
    """

    _cmd = ""
    _tcpdump = None

    _devname = None
    _file    = None
    _filter  = None

    def set_interface(self, devname):
        self._devname = devname

    def set_output_file(self, file_path):
        self._file = file_path

    def set_filter(self, filt):
        self._filter = filt

    def start(self):
        self._run()

    def stop(self):
        """ Send SIGTERM to the background instance of
            tcpdump.
        """
        self._tcpdump.terminate()

    def _compose_cmd(self):
        """ Create a command from the options """
        interface = self._devname
        output_file = self._file
        pcap_filter = self._filter

        self._cmd = "tcpdump -p -i %s -w %s \"%s\"" % (interface, output_file,
                                                        pcap_filter)

    def _execute_tcpdump(self):
        """ Start tcpdump in the background """
        cmd = self._cmd
        self._tcpdump = subprocess.Popen(cmd, shell=True, stdout=None,
                                            stderr=None)

    def _run(self):
        self._compose_cmd()
        self._execute_tcpdump()
