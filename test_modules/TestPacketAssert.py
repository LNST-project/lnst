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
from lnst.Common.TestsCommon import TestGeneric

class TestPacketAssert(TestGeneric):
    """ Assert for number of incomming/outgoing packets
        Capturing backend of this class is provided by
        tcpdump(8).
    """

    _cmd = ""
    _tcpdump = None
    _grep_filters = []

    _min_cond = 1
    _max_cond = None

    _num_recv = 0

    def _set_interrupt_handler(self):
        signal.signal(signal.SIGINT, self._interrupt_handler)
        signal.signal(signal.SIGTERM, self._interrupt_handler)

    def _interrupt_handler(self, signum, frame):
        """ Kill tcpdump when interrupted """
        self._tcpdump.terminate()

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
        pcap_filter = self.get_mopt("filter")

        cmd = "tcpdump -p -nn -i %s \"%s\"" % (interface, pcap_filter)
        self._cmd = cmd

    def _execute_tcpdump(self):
        """ Start tcpdump in the background """
        cmd = self._cmd
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
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

        line = ""
        tcpdump_output = self._tcpdump.stdout
        while True:
            if self._tcpdump.poll() != None:
                if self._tcpdump.returncode > 0:
                    raise Exception("tcpdump terminated with error")
                else:
                    break

            try:
                next_line = tcpdump_output.readline()
            except IOError: # Interrupted system call
                continue

            if next_line == "":
                continue

            next_line = next_line.strip("\n")

            if re.match("[0-9]+\:[0-9]+\:[0-9\.]+", next_line) and line != "":
                self._process_captured_line(line)
                line = next_line
            else:
                line += next_line

        logging.info("Capturing finished. Received %d packets", self._num_recv)
        res = {"received": self._num_recv,
               "min": self._min_cond,
               "max": self._max_cond}

        if self._evaluate_results():
            return self.set_pass(res)

        return self.set_fail("PacketAssert failed!", res)
