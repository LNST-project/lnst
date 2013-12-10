"""
This module defines TCPConnection test,
a python wrapper for LNST's tcp_conn test tool
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import re
import errno
import logging
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.Utils import bool_it

class TCPConnection(TestGeneric):
    def run(self):
        mode = self.get_mopt("mode")
        address = self.get_mopt("address")
        portrange = self.get_mopt("portrange")

        continuous = self.get_opt("continuous")
        debug = self.get_opt("debug")
        ipv6 = self.get_opt("ipv6")

        cmd = ""
        if (mode == "server"):
            logging.debug("TCPConnection: running as server")
            cmd += "./tcp_listen"
        elif (mode == "client"):
            logging.debug("TCPConnection: running as client")
            cmd += "./tcp_connect"
        else:
            raise Exception("Invalid mode value for TCPConnection test module!")

        cmd += " -a %s -p %s" % (address, portrange)

        if continuous and bool_it(continuous):
            cmd += " -c"

        if debug and bool_it(debug):
            cmd += " -d"

        if ipv6 and bool_it(ipv6):
            cmd += " -6"

        output = self.exec_from("tcp_conn", cmd, die_on_err=False, log_outputs=True)[0]

        logging.debug("TCPConnection done, inspecting logs ...")

        m = None
        if (mode == "client"):
            m = re.search("made [0-9]* connections", output)
        elif (mode == "server"):
            m = re.search("handled [0-9]* connections", output)

        if m is None:
            return self.set_fail({'msg': "Unexpected error"})
        else:
            return self.set_pass({'msg': m.group(0)})
