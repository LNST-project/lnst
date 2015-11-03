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
from lnst.Common.Utils import std_deviation, is_installed

class Netperf(TestGeneric):

    supported_tests = ["TCP_STREAM", "TCP_RR", "UDP_STREAM", "UDP_RR",
                       "SCTP_STREAM", "SCTP_STREAM_MANY", "SCTP_RR"]

    def __init__(self, command):
        super(TestGeneric, self).__init__(command)

        self._role = self.get_mopt("role")

        if self._role == "client":
            self._netperf_server = self.get_mopt("netperf_server",
                                                 opt_type="addr")

        self._netperf_opts = self.get_opt("netperf_opts")
        self._duration = self.get_opt("duration")
        self._port = self.get_opt("port")
        self._testname = self.get_opt("testname", default="TCP_STREAM")
        self._confidence = self.get_opt("confidence")
        self._bind = self.get_opt("bind", opt_type="addr")
        self._family = self.get_opt("family")

        self._runs = self.get_opt("runs", default=1)
        if self._runs > 1 and self._confidence is not None:
            logging.warning("Ignoring 'runs' because 'confidence' "\
                            "was specified.")
            self._runs = 1

        self._threshold = self._parse_threshold(self.get_opt("threshold"))
        self._threshold_deviation = self._parse_threshold(
                                        self.get_opt("threshold_deviation"))
        if self._threshold_deviation is None:
            self._threshold_deviation = {"rate" : 0.0,
                                         "unit" : "bps"}

        if self._threshold is not None:
            rate = self._threshold["rate"]
            deviation = self._threshold_deviation["rate"]
            self._threshold_interval = (rate - deviation,
                                        rate + deviation)
        else:
            self._threshold_interval = None

    def _compose_cmd(self):
        """
        composes commands for netperf and netserver based on xml recipe
        """
        if self._role == "client":
            cmd = "netperf -H %s -f k" % self._netperf_server
            if self._port is not None:
                """
                client connects on this port
                """
                cmd += " -p %s" % self._port
            if self._duration is not None:
                """
                test will last this duration
                """
                cmd += " -l %s" % self._duration
            if self._testname is not None:
                """
                test that will be performed
                """
                if self._testname not in self.supported_tests:
                    logging.warning("Only TCP_STREAM, TCP_RR, UDP_STREAM, "
                    "UDP_RR, SCTP_STREAM, SCTP_STREAM_MANY and SCTP_RR tests "
                    "are now officialy supported by LNST. You "
                    "can use other tests, but test result may not be correct.")
                cmd += " -t %s" % self._testname

            if self._confidence is not None:
                """
                confidence level that Netperf should try to achieve
                """
                cmd += " -I %s" % self._confidence

            if self._netperf_opts is not None:
                """
                custom options for netperf
                """
                cmd += " %s" % self._netperf_opts
        elif self._role == "server":
            cmd = "netserver -D"
            if self._bind is not None:
                """
                server is bound to this address
                """
                cmd += " -L %s" % self._bind
            if self._port is not None:
                """
                server listens on this port
                """
                cmd += " -p %s" % self._port
            if self._netperf_opts is not None:
                """
                custom options for netperf
                """
                cmd += " %s" % self._netperf_opts
        return cmd

    def _parse_output(self, output):
        if self._testname == "UDP_STREAM":
            # pattern for UDP_STREAM throughput output
            # decimal float decimal (float)
            pattern_udp_stream = "\d+\s+\d+\.\d+\s+\d+\s+(\d+(\.\d+){0,1})\n"
            r2 = re.search(pattern_udp_stream, output.lower())
        elif self._testname == "TCP_STREAM":
            # pattern for TCP_STREAM throughput output
            # decimal decimal decimal float (float)
            pattern_tcp_stream = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_tcp_stream, output.lower())
        elif self._testname == "TCP_RR" or self._testname == "UDP_RR"\
             or self._testname == "SCTP_RR":
            # pattern for TCP_RR, UDP_RR and SCTP_RR throughput output
            # decimal decimal decimal decimal float (float)
            pattern_tcp_rr = "\d+\s+\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_tcp_rr, output.lower())
        else:
            # pattern for SCTP streams and other tests
            # decimal decimal decimal float (float)
            pattern_sctp = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(\.\d+){0,1})"
            r2 = re.search(pattern_sctp, output.lower())

        if r2 is None:
            rate_in_kb = 0.0
        else:
            rate_in_kb = float(r2.group(1))

        if self._confidence is not None:
            confidence = self._parse_confidence(output)
            return {"rate": rate_in_kb*1000,
                    "unit": "bps",
                    "confidence": confidence}
        else:
            return {"rate": rate_in_kb*1000,
                    "unit": "bps"}

    def _parse_confidence(self, output):
        normal_pattern = r'\+/-(\d+\.\d*)% @ (\d+)% conf\.'
        warning_pattern = r'!!! Confidence intervals: Throughput\s+: (\d+\.\d*)%'
        normal_confidence = re.search(normal_pattern, output)
        warning_confidence = re.search(warning_pattern, output)

        if normal_confidence is None:
            logging.error("Failed to parse confidence!!")
            return (0, 0.0)

        if warning_confidence is None:
            real_confidence = (float(normal_confidence.group(2)),
                               float(normal_confidence.group(1)))
        else:
            real_confidence = (float(normal_confidence.group(2)),
                               float(warning_confidence.group(1))/2)

        return real_confidence


    def _parse_threshold(self, threshold):
        res_data = {}

        if threshold is None:
            return None
        # pattern for threshold
        # group(1) ... threshold value
        # group(3) ... threshold units
        # group(4) ... bytes/bits
        if (self._testname == "TCP_STREAM" or
            self._testname == "UDP_STREAM" or
            self._testname == "SCTP_STREAM" or
            self._testname == "SCTP_STREAM_MANY"):
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
        elif (self._testname == "TCP_RR" or self._testname == "UDP_RR" or
              self._testname == "SCTP_RR"):
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
        res_data["testname"] = self._testname

        rv = 0
        results = []
        rates = []
        for i in range(1, self._runs+1):
            if self._runs > 1:
                logging.info("Netperf starting run %d" % i)
            client = ShellProcess(cmd)
            try:
                ret_code = client.wait()
                rv += ret_code
            except OSError as e:
                if e.errno == errno.EINTR:
                    client.kill()

            output = client.read_nonblocking()

            if ret_code == 0:
                results.append(self._parse_output(output))
                rates.append(results[-1]["rate"])

        if results > 1:
            res_data["results"] = results

        if len(rates) > 0:
            rate = sum(rates)/len(rates)
        else:
            rate = 0.0

        if len(rates) > 1:
            rate_deviation = std_deviation(rates)
        elif len(rates) == 1 and self._confidence is not None:
            result = results[0]
            rate_deviation = rate * (result["confidence"][1] / 100)
        else:
            rate_deviation = 0.0

        res_data["rate"] = rate
        res_data["rate_deviation"] = rate_deviation

        res_val = False
        if self._threshold_interval is not None:
            result_interval = (rate - rate_deviation,
                               rate + rate_deviation)

            if self._threshold_interval[0] > result_interval[1]:
                res_val = False
                res_data["msg"] = "Measured rate %.2f +-%.2f bps is lower "\
                                  "than threshold %.2f +-%.2f" %\
                                  (rate, rate_deviation,
                                   self._threshold["rate"],
                                   self._threshold_deviation["rate"])
            else:
                res_val = True
                res_data["msg"] = "Measured rate %.2f +-%.2f bps is higher "\
                                  "than threshold %.2f +-%.2f" %\
                                  (rate, rate_deviation,
                                   self._threshold["rate"],
                                   self._threshold_deviation["rate"])
        else:
            if rate > 0.0:
                res_val = True
            else:
                res_val = False
            res_data["msg"] = "Measured rate was %.2f +-%.2f bps" %\
                                                (rate, rate_deviation)

        if rv != 0 and self._runs == 1:
            res_data["msg"] = "Could not get performance throughput!"
            logging.info(res_data["msg"])
            return (False, res_data)
        elif rv != 0 and self._runs > 1:
            res_data["msg"] = "At least one of the Netperf runs failed, "\
                              "check the logs and result data for more "\
                              "information."
            logging.info(res_data["msg"])
            return (False, res_data)
        return (res_val, res_data)

    def run(self):
        cmd = self._compose_cmd()
        logging.debug("compiled command: %s" % cmd)
        if self._role == "client":
            if not is_installed("netperf"):
                res_data = {}
                res_data["msg"] = "Netperf is not installed on this machine!"
                logging.error(res_data["msg"])
                return self.set_fail(res_data)

            (rv, res_data) = self._run_client(cmd)
            if rv == False:
                return self.set_fail(res_data)
            return self.set_pass(res_data)
        elif self._role == "server":
            if not is_installed("netserver"):
                res_data = {}
                res_data["msg"] = "Netserver is not installed on this machine!"
                logging.error(res_data["msg"])
                return self.set_fail(res_data)
            self._run_server(cmd)
