"""
Test if packets were transfered through some interface correctly.
This test is using tcpdump.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import subprocess
import re
import signal
import time
import os
import tempfile
from lnst.Common.TestsCommon import TestGeneric

class PacketAssert(TestGeneric):
    """ Assert for number of incomming/outgoing packets
        Capturing backend of this class is provided by
        tcpdump(8).
    """

    _cmd = ""
    _tcpdump = None
    _tcpdump_capture_file = None
    _grep_filters = []

    _min_cond = 1
    _max_cond = None

    _num_recv = 0

    def _set_interrupt_handler(self):
        signal.signal(signal.SIGINT, self._interrupt_handler)
        signal.signal(signal.SIGTERM, self._interrupt_handler)

    def _interrupt_handler(self, signum, frame):
        """ Kill tcpdump when interrupted """
        try:
            self._tcpdump.terminate()
        except OSError:
            raise Exception("Caught exception in interrupt handler")

    def _prepare_grep_filters(self):
        """ Parse `grep_for' test options """
        filters = self.get_multi_opt("grep_for")

        for filt in filters:
            if filt != None:
                self._grep_filters.append(filt)

    def _prepare_conditions(self):
        """ Parse `min' and `max' """
        min_packets = self.get_opt("min")
        max_packets = self.get_opt("max")

        if min_packets != None:
            self._min_cond = int(min_packets)

        if max_packets != None:
            self._max_cond = int(max_packets)

    def _compose_cmd(self):
        """ Create a command from the recipe options """
        cmd  = ""

        interface = self.get_mopt("interface")
        pcap_filter = self.get_opt("filter")
        if not pcap_filter:
            pcap_filter = ""

        cmd = "tcpdump -p -nn -i %s \"%s\"" % (interface, pcap_filter)
        self._cmd = cmd

    def _execute_tcpdump(self):
        """ Start tcpdump in the background """
        cmd = self._cmd
        tcpdump_file = tempfile.NamedTemporaryFile(delete=False)
        self._tcpdump_capture_file = tcpdump_file.name

        proc = subprocess.Popen(cmd, shell=True, stdout=tcpdump_file,
                                    stderr=None)
        self._tcpdump = proc

    def _process_captured_line(self, line):
        """ Apply filters and see if the packet passed them """
        if len(self._grep_filters):
            for filt in self._grep_filters:
                if not re.search(filt, line):
                    return

        self._num_recv += 1

    def _evaluate_results(self):
        """ Compare results with the conditions """
        num = self._num_recv
        if num >= self._min_cond:
            if self._max_cond != None:
                return num <= self._max_cond
            return True
        return False

    def run(self):
        self._set_interrupt_handler()

        self._prepare_grep_filters()
        self._prepare_conditions()
        self._compose_cmd()
        self._execute_tcpdump()

        logging.info("Capturing started")

        while True:
            if self._tcpdump.poll() != None:
                if self._tcpdump.returncode > 0:
                    raise Exception("tcpdump terminated with error")
                else:
                    break
            else:
                time.sleep(1)
                continue

        # get and evalute the tcpdump's output
        # empty string returned by readline() means the EOF has been reached
        tcpdump_file = open(self._tcpdump_capture_file, 'r')
        line = "\n"
        while line != "":
            try:
                line = tcpdump_file.readline()
            except (OSError, IOError):
                logging.debug("Caught exception while reading tcpdump output")
                break

            line = line.strip("\n")
            self._process_captured_line(line)

        tcpdump_file.close()
        os.remove(tcpdump_file.name)

        logging.info("Capturing finished. Received %d packets", self._num_recv)
        res = {"received": self._num_recv,
               "min": self._min_cond,
               "max": self._max_cond}

        if self._evaluate_results():
            return self.set_pass(res)

        res["msg"] = "PacketAssert failed!"
        return self.set_fail(res)
