"""
This module defines netcat stream test

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import re
import time
import logging
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ShellProcess import ShellProcess

class TestNetCat(TestGeneric):
    def _get_stream(self):
        return self.get_opt("stream", default="tcp")

    def _compose_nc_cmd(self):
        cmd = "yes | nc -v"

        if self._get_stream() == "udp":
            cmd += " -u"

        ipv = self.get_opt("ipv") # IP protocol version - 4 or 6
        if ipv:
            cmd += " -%s" % ipv

        addr = self.get_mopt("addr", opt_type="addr")
        port = self.get_mopt("port")
        cmd += " %s %s" % (addr, port)

        return cmd

    def _compose_tcpdump_cmd(self):
        cmd = ("tcpdump -c 10 -i any %s port %s and host %s" %
                    (self._get_stream(),
                     self.get_mopt("port"),
                     self.get_mopt("addr", opt_type="addr")))
        return cmd

    def run(self):
        nc = ShellProcess(self._compose_nc_cmd())

        # check whether anything is being sent over the line
        td = ShellProcess(self._compose_tcpdump_cmd())

        try:
            td.read_until_output_matches("10 packets captured", timeout=5)
        except ShellProcess.ProcessTerminatedError:
            res_data = {"msg": "tcpdump process died unexpectedly!"}
            return self.set_fail(res_data)
        except ShellProcess.ProcessTimeoutError:
            res_data = {"msg": "No stream detected!"}
            return self.set_fail(res_data)

        td.kill()

        duration = self.get_opt("duration", default=30)
        time.sleep(duration)

        nc.kill()

        logging.info("nc stream with duration of %s secs" % duration)
        return self.set_pass()
