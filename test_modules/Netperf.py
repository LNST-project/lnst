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
from lnst.Common.Utils import std_deviation

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
            cmd = "netperf -H %s -f k" % netperf_server
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

    def _parse_output(self, output):
        testname = self.get_opt("testname")
        if testname == "UDP_STREAM":
            # pattern for UDP_STREAM throughput output
            # decimal float decimal (float)
            pattern_udp_stream = "\d+\s+\d+\.\d+\s+\d+\s+(\d+(\.\d+){0,1})\n"
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

        rate_in_kb = float(r2.group(1))

        return {"rate": rate_in_kb*1000,
                "unit": "bps"}


    def _parse_threshold(self, threshold):
        if threshold is None:
            return None
        # pattern for threshold
        # group(1) ... threshold value
        # group(3) ... threshold units
        # group(4) ... bytes/bits
        if (testname == "TCP_STREAM" or testname == "UDP_STREAM" or
           testname == "SCTP_STREAM" or testname == "SCTP_STREAM_MANY"):
            pattern_stream = "(\d*(\.\d*)?)\s*([ kmgtKMGT])(bits|bytes)\/sec"
            r1 = re.search(pattern_stream, threshold)
            if r1 is None:
                res_data["msg"] = "Invalid unit type in the "\
                                  "throughput option"
                return (False, res_data)
            threshold_rate = float(r1.group(1))
            threshold_unit_size = r1.group(3)
            threshold_unit_type = r1.group(4)
            if threshold_unit_size == 'k':
                threshold_rate *= 1000
            elif threshold_unit_size == 'K':
                threshold_rate *= 1024
            elif threshold_unit_size == 'g':
                threshold_rate *= 1000*1000
            elif threshold_unit_size == 'G':
                threshold_rate *= 1024*1024
            elif threshold_unit_size == 't':
                threshold_rate *= 1000 * 1000 * 1000
            elif threshold_unit_size == 'T':
                threshold_rate *= 1024 * 1024 * 1024
            if threshold_unit_type == "bytes":
                threshold_rate *= 8
            threshold_unit_type = "bps"
        elif (testname == "TCP_RR" or testname == "UDP_RR" or
             testname == "SCTP_RR"):
            pattern_rr =  "(\d*(\.\d*)?)\s*trans\.\/sec"
            r1 = re.search(pattern_rr, threshold.lower())
            if r1 is None:
                res_data["msg"] = "Invalid unit type in the "\
                                  "throughput option"
                return (False, res_data)
            threshold_rate = float(r1.group(1))
            threshold_unit_size = ""
            threshold_unit_type = "tps"

        return {"rate": threshold_rate,
                "unit": threshold_unit_type}

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

        res_data = {}

        rv = 0
        runs = self.get_opt("runs", default=1)
        results = []
        rates = []
        for i in range(1, runs+1):
            if runs > 1:
                logging.info("Netperf starting run %d" % i)
            client = ShellProcess(cmd)
            try:
                rv += client.wait()
            except OSError as e:
                if e.errno == errno.EINTR:
                    client.kill()
            output = client.read_nonblocking()
            results.append(self._parse_output(output))
            rates.append(results[-1]["rate"])

        if runs > 1:
            res_data["results"] = results

        rate = sum(rates)/len(rates)
        rate_std_deviation = std_deviation(rates)
        res_data["rate"] = rate
        res_data["rate_std_deviation"] = rate_std_deviation

        threshold = self._parse_threshold(self.get_opt("threshold"))
        threshold_std_deviation = self._parse_threshold(self.get_opt("threshold_std_deviation"))

        res_val = False
        if threshold is not None:
            threshold = threshold["rate"]
            if threshold_std_deviation is None:
                threshold_std_deviation = 0.0
            else:
                threshold_std_deviation = threshold_std_deviation["rate"]
            result_interval = (rate - rate_std_deviation,
                               rate + rate_std_deviation)
            threshold_interval = (threshold - threshold_std_deviation,
                                  threshold + threshold_std_deviation)

            if threshold_interval[0] > result_interval[1]:
                res_val = False
                res_data["msg"] = "Measured rate %.2f +-%.2f bps is lower "\
                                  "than threshold %.2f +-%.2f" %\
                                  (rate, rate_std_deviation,
                                   threshold, threshold_std_deviation)
            else:
                res_val = True
                res_data["msg"] = "Measured rate %.2f +-%.2f bps is higher "\
                                  "than threshold %.2f +-.2%f" %\
                                  (rate, rate_std_deviation,
                                   threshold, threshold_std_deviation)
        else:
            if rate > 0.0:
                res_val = True
            else:
                res_val = False
            res_data["msg"] = "Measured rate was %.2f +-%.2f bps" %\
                                                (rate, rate_std_deviation)

        if rv != 0:
            res_data["msg"] = "Could not get performance throughput! Are you "\
                              "sure netperf is installed on both machines and "\
                              "machines are mutually accessible?"
            logging.info(res_data["msg"])
            return (False, res_data)
        return (res_val, res_data)

    def run(self):
        self.role = self.get_mopt("role")
        cmd = self._compose_cmd(self.role)
        logging.debug("compiled command: %s" % cmd)
        if self.role == "client":
            (rv, res_data) = self._run_client(cmd)
            if rv == False:
                return self.set_fail(res_data)
            return self.set_pass(res_data)
        elif self.role == "server":
            self._run_server(cmd)
