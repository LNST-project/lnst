"""
Netperf test module
"""

__author__ = """
jprochaz@redhat.com (Jiri Prochazka)
"""

import logging
import errno
import re
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ShellProcess import ShellProcess

class Netperf(TestGeneric):

    def _compose_cmd(self, role):
        """
        composes commands for netperf and netserver based on xml recipe
        """
        netperf_opts = self.get_opt("netperf_opts")
        if role == "client":
            netperf_server = self.get_mopt("netperf_server", opt_type="addr")
            duration = self.get_opt("duration")
            port = self.get_opt("port")
            cmd = "netperf -H %s" % netperf_server
            if port is not None:
                """
                client connects on this port
                """
                cmd += " -p %s" % port
            if duration is not None:
                """
                test will last this duration
                """
                cmd += " -l %s" % duration
            if netperf_opts is not None:
                """
                custom options for netperf
                """
                cmd += " %s" % netperf_opts
        elif role == "server":
            bind = self.get_opt("bind", opt_type="addr")
            port = self.get_opt("port")
            family = self.get_opt("family")
            cmd = "netserver -D"
            if bind is not None:
                """
                server is bound to this address
                """
                cmd += " -L %s" % bind
            if port is not None:
                """
                server listens on this port
                """
                cmd += " -p %s" % port
            if netperf_opts is not None:
                """
                custom options for netperf
                """
                cmd += " %s" % netperf_opts
        return cmd

    def _parse_output(self, threshold, output):
        # pattern for throughput output
        pattern2 = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
        r2 = re.search(pattern2, output.lower())
        if r2 is None:
            """
            throughput was not found, end test with failure
            """
            logging.info("Could not get performance throughput! Are you sure "\
                         "netperf is installed on both machines and machines "\
                         "are mutually accessible?")
            return (False, "Could not get performance throughput! Are you "\
                           "sure netperf is installed on both machines and "\
                           "machines are mutually accessible?")
        if threshold is not None:
            # pattern for threshold
            # group(1) ... threshold value
            # group(3) ... threshold units
            # group(4) ... bytes/bits
            pattern1 = "(\d*(\.\d*){0,1})\s*([ kmgt])(bits|bytes)\/sec"
            r1 = re.search(pattern1, threshold.lower())
            threshold_rate = float(r1.group(1))
            threshold_unit_size = r1.group(3)
            threshold_unit_type = r1.group(4)
            throughput_rate = float(r2.group(1))
            """
            this part converts threshold and throughput rates to same format
            user will get output in format specified in threshold option
            if no threshold option is put in, default format is Mbits
            """
            if threshold_unit_size == 'k':
                throughput_rate *= 1000
            elif threshold_unit_size == 'g':
                throughput_rate /= 1000
            elif threshold_unit_size == 't':
                throughput_rate /= 1000 * 1000
            if threshold_unit_type == "bytes":
                throughput_rate /= 8
            if threshold_rate > throughput_rate:
                return (False, "Measured rate (%s %s%s) is below threshold "\
                               "(%s %s%s)!" % (throughput_rate,
                                               threshold_unit_size.upper(),
                                               threshold_unit_type,
                                               threshold_rate,
                                               threshold_unit_size.upper(),
                                               threshold_unit_type))
            else:
                return (True, "Measured rate (%s %s%s) is over threshold "\
                              "(%s %s%s)." % (throughput_rate,
                                              threshold_unit_size.upper(),
                                              threshold_unit_type,
                                              threshold_rate,
                                              threshold_unit_size.upper(),
                                              threshold_unit_type))
        else:
            return (True, "Measured rate: %s Mbits" % r2.group(1))



    def _run_server(self, cmd):
        logging.debug("running as server...")
        server = ShellProcess(cmd)
        try:
            server.wait()
        except OSError as e:
            if e.errno == errno.EINTR:
                server.kill()

    def _run_client(self, cmd):
        logging.debug("running as client...")
        client = ShellProcess(cmd)
        try:
            client.wait()
        except OSError as e:
            if e.errno == errno.EINTR:
                client.kill()
        output = client.read_nonblocking()
        return self._parse_output(self.get_opt("threshold"), output)

    def run(self):
        self.role = self.get_mopt("role")
        cmd = self._compose_cmd(self.role)
        logging.debug("compiled command: %s" % cmd)
        if self.role == "client":
            (rv, message) = self._run_client(cmd)
            res_data = {"msg" : message}
            if rv == False:
                return self.set_fail(res_data)
            return self.set_pass(res_data)
        elif self.role == "server":
            self._run_server(cmd)
