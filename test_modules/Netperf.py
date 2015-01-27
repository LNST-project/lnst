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

    supported_tests = ["TCP_STREAM", "TCP_RR", "UDP_STREAM", "UDP_RR",
                       "SCTP_STREAM", "SCTP_STREAM_MANY", "SCTP_RR"]

    def _compose_cmd(self, role):
        """
        composes commands for netperf and netserver based on xml recipe
        """
        netperf_opts = self.get_opt("netperf_opts")
        if role == "client":
            netperf_server = self.get_mopt("netperf_server", opt_type="addr")
            duration = self.get_opt("duration")
            port = self.get_opt("port")
            testname = self.get_opt("testname")
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
            if testname is not None:
                """
                test that will be performed
                """
                if testname not in self.supported_tests:
                    logging.warning("Only TCP_STREAM, TCP_RR, UDP_STREAM, "
                    "UDP_RR, SCTP_STREAM, SCTP_STREAM_MANY and SCTP_RR tests "
                    "are now officialy supported by LNST. You "
                    "can use other tests, but test result may not be correct.")
                cmd += " -t %s" % testname

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
        testname = self.get_opt("testname")
        if testname == "UDP_STREAM":
            # pattern for UDP_STREAM throughput output
            # decimal decimal float decimal decimal (float)
            pattern_udp_stream = "\d+\s+\d+\s+\d+\.\d+\s+\d+\s+\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_udp_stream, output.lower())
        elif testname == "TCP_STREAM":
            # pattern for TCP_STREAM throughput output
            # decimal decimal decimal float (float)
            pattern_tcp_stream = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_tcp_stream, output.lower())
        elif testname == "TCP_RR" or testname == "UDP_RR" or testname == "SCTP_RR":
            # pattern for TCP_RR, UDP_RR and SCTP_RR throughput output
            # decimal decimal decimal decimal float (float)
            pattern_tcp_rr = "\d+\s+\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_tcp_rr, output.lower())
        else:
            # pattern for SCTP streams and other tests
            # decimal decimal decimal float (float)
            pattern_sctp = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_sctp, output.lower())
        if threshold is not None:
            # pattern for threshold
            # group(1) ... threshold value
            # group(3) ... threshold units
            # group(4) ... bytes/bits
            if (testname == "TCP_STREAM" or testname == "UDP_STREAM" or
               testname == "SCTP_STREAM" or testname == "SCTP_STREAM_MANY"):
                pattern_stream = "(\d*(\.\d*){0,1})\s*([ kmgt])(bits|bytes)\/sec"
                r1 = re.search(pattern_stream, threshold.lower())
                if r1 is None:
                    return (False, "Invalid unit type in the throughput option")
                threshold_rate = float(r1.group(1))
                threshold_unit_size = r1.group(3)
                threshold_unit_type = r1.group(4)
            elif (testname == "TCP_RR" or testname == "UDP_RR" or
                 testname == "SCTP_RR"):
                pattern_rr =  "(\d*(\.\d*){0,1})\s*trans\.\/sec"
                r1 = re.search(pattern_rr, threshold.lower())
                if r1 is None:
                    return (False, "Invalid unit type in the throughput option")
                threshold_rate = float(r1.group(1))
                threshold_unit_size = ""
                threshold_unit_type = "Trans./sec"
            throughput_rate = float(r2.group(1))
            """
            this part converts threshold and throughput rates to same format
            user will get output in format specified in threshold option
            if no threshold option is put in, default format is Mbits
            """
            if (testname == "UDP_STREAM" or testname == "TCP_STREAM" or
               testname == "SCTP_STREAM" or testname == "SCTP_STREAM_MANY"):
                if threshold_unit_size == 'k':
                    throughput_rate *= 1000
                elif threshold_unit_size == 'g':
                    throughput_rate /= 1000
                elif threshold_unit_size == 't':
                    throughput_rate /= 1000 * 1000
                if threshold_unit_type == "bytes":
                    throughput_rate /= 8
            if threshold_rate > throughput_rate:
                return (False, "Measured rate (%s %s%s) is below threshold "
                               "(%s %s%s)!" % (throughput_rate,
                                               threshold_unit_size.upper(),
                                               threshold_unit_type,
                                               threshold_rate,
                                               threshold_unit_size.upper(),
                                               threshold_unit_type))
            else:
                return (True, "Measured rate (%s %s%s) is over threshold "
                              "(%s %s%s)." % (throughput_rate,
                                              threshold_unit_size.upper(),
                                              threshold_unit_type,
                                              threshold_rate,
                                              threshold_unit_size.upper(),
                                              threshold_unit_type))
        else:
            if (testname == "TCP_RR" or testname == "UDP_RR" or
               testname == "SCTP_RR"):
                return (True, "Measured rate: %s Trans./sec" % r2.group(1))
            else:
                return (True, "Measured rate: %s Mbits/sec" % r2.group(1))



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
            rv = client.wait()
        except OSError as e:
            if e.errno == errno.EINTR:
                client.kill()
        output = client.read_nonblocking()
        if rv != 0:
            logging.info("Could not get performance throughput! Are you sure "
                         "netperf is installed on both machines and machines "
                         "are mutually accessible?")
            return (False, "Could not get performance throughput! Are you "
                           "sure netperf is installed on both machines and "
                           "machines are mutually accessible?")
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
