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
from lnst.Common.Utils import std_deviation, is_installed, int_it

class Netperf(TestGeneric):

    supported_tests = ["TCP_STREAM", "TCP_RR", "UDP_STREAM", "UDP_RR",
                       "SCTP_STREAM", "SCTP_STREAM_MANY", "SCTP_RR"]

    omni_tests = ["TCP_STREAM", "TCP_RR", "UDP_STREAM", "UDP_RR"]

    def __init__(self, command):
        super(Netperf, self).__init__(command)

        self._role = self.get_mopt("role")

        if self._role == "client":
            self._netperf_server = self.get_mopt("netperf_server",
                                                 opt_type="addr")

        self._netperf_opts = self.get_opt("netperf_opts")
        self._duration = self.get_opt("duration")
        self._port = self.get_opt("port")
        self._testname = self.get_opt("testname", default="TCP_STREAM")
        self._testoptions = self.get_opt("testoptions")
        self._confidence = self.get_opt("confidence")
        self._bind = self.get_opt("bind", opt_type="addr")
        self._cpu_util = self.get_opt("cpu_util")
        self._num_parallel = int(self.get_opt("num_parallel", default=1))
        self._runs = self.get_opt("runs", default=1)
        self._msg_size = self.get_opt("msg_size")
        self._debug = int_it(self.get_opt("debug", default=0))

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

        self._max_deviation = self._parse_max_deviation(
                                self.get_opt("max_deviation", default=None))

    def _is_omni(self):
        return self._testname in self.omni_tests

    def _compose_cmd(self):
        """
        composes commands for netperf and netserver based on xml recipe
        """
        if self._role == "client":
            # for request response test transactions per seconds are used as unit
            if "RR" in self._testname:
                cmd = "netperf -H %s -f x" % self._netperf_server
            # else 10^0bits/s are used as unit
            else:
                cmd = "netperf -H %s -f b" % self._netperf_server
            if self._is_omni():
                # -P 0 disables banner header of output
                cmd += " -P 0"
            if self._bind is not None:
                """
                application is bound to this address
                """
                cmd += " -L %s" % self._bind
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

            if self._confidence is not None and self._num_parallel <= 1:
                """
                confidence level that Netperf should try to achieve
                """
                cmd += " -I %s" % self._confidence
                if self._runs >= 3:
                    cmd += " -i %d,%d" % (self._runs, self._runs)
                    self._runs = 1

            if self._cpu_util is not None:
                if self._cpu_util.lower() == "both":
                    cmd += " -c -C"
                elif self._cpu_util.lower() == "local":
                    cmd += " -c"
                elif self._cpu_util.lower() == "remote":
                    cmd += " -C"

            if self._debug > 0:
                cmd += " -%s" % ('d' * self._debug)

            if self._netperf_opts is not None:
                """
                custom options for netperf
                """
                cmd += " %s" % self._netperf_opts

            if self._num_parallel > 1:
                """
                wait 1 second before starting the data transfer
                taken from the super_netperf script, can be removed if it
                doesn't make sense
                """
                cmd += " -s 1"

            # Print only relevant output
            if self._is_omni():
                cmd += ' -- -k "THROUGHPUT, THROUGHPUT_UNITS, '\
                       'LOCAL_CPU_UTIL, REMOTE_CPU_UTIL, '\
                       'CONFIDENCE_LEVEL, THROUGHPUT_CONFID, LOCAL_SEND_SIZE, '\
                       'REMOTE_RECV_SIZE, LOCAL_SEND_THROUGHPUT, '\
                       'REMOTE_RECV_THROUGHPUT, LOCAL_CPU_PEAK_UTIL, '\
                       'REMOTE_CPU_PEAK_UTIL"'

            if self._testoptions:
                if self._is_omni():
                    cmd += " %s" % self._testoptions
                else:
                    cmd += " -- %s" % self._testoptions

            if self._msg_size is not None:
                """
                packets will have this size
                """
                if self._is_omni() or self._testoptions:
                    cmd += " -m %s" % self._msg_size
                else:
                    cmd += " -- -m %s" % self._msg_size


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
        res_val = None

        if self._is_omni():
            res_val = self._parse_omni_output(output)
        else:
            res_val = self._parse_non_omni_output(output)

        if self._confidence is not None:
            confidence = self._parse_confidence(output)
            res_val["confidence"] = confidence

        return res_val

    def _parse_omni_output(self, output):
        res_val = {}

        pattern_throughput = "THROUGHPUT=(\d+\.\d+)"
        throughput = re.search(pattern_throughput, output)

        pattern_throughput_units = "THROUGHPUT_UNITS=(.*)"
        throughput_units = re.search(pattern_throughput_units, output).group(1)

        if throughput is None:
            rate = 0.0
        else:
            rate = float(throughput.group(1))

        if throughput_units == "10^0bits/s":
            res_val["unit"] = "bps"
        elif throughput_units == "Trans/s":
            res_val["unit"] = "tps"

        res_val["rate"] = rate

        if self._cpu_util is not None:
            if self._cpu_util == "local" or self._cpu_util == "both":
                pattern_loc_cpu_util = "LOCAL_CPU_UTIL=([-]?\d+\.\d+)"
                loc_cpu_util = re.search(pattern_loc_cpu_util, output)
                res_val["LOCAL_CPU_UTIL"] = float(loc_cpu_util.group(1))

            if self._cpu_util == "remote" or self._cpu_util == "both":
                pattern_rem_cpu_util = "REMOTE_CPU_UTIL=([-]?\d+\.\d+)"
                rem_cpu_util = re.search(pattern_rem_cpu_util, output)
                res_val["REMOTE_CPU_UTIL"] = float(rem_cpu_util.group(1))

        return res_val

    def _parse_non_omni_output(self, output):
        res_val = {}

        # pattern for SCTP streams and other tests
        # decimal decimal decimal float (float)
        pattern = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(?:\.\d+){0,1})"
        if self._cpu_util != 'None':
            # cpu utilization data in format: float float
            pattern += "\s+(\d+(?:\.\d+){0,1})\s+(\d+(?:\.\d+){0,1})"

        r2 = re.search(pattern, output.lower())

        if r2 is None:
            rate = 0.0
        else:
            rate = float(r2.group(1))
            if self._cpu_util != 'None':
                res_val["LOCAL_CPU_UTIL"] = float(r2.group(2))
                res_val["REMOTE_CPU_UTIL"] = float(r2.group(3))

        res_val["rate"] = rate
        res_val["unit"] = "bps"

        return res_val

    def _parse_confidence(self, output):
        if self._is_omni():
            return self._parse_confidence_omni(output)
        else:
            return self._parse_confidence_non_omni(output)

    def _parse_confidence_omni(self, output):
        pattern_throughput_confid = "THROUGHPUT_CONFID=([-]?\d+\.\d+)"
        pattern_confidence_level = "CONFIDENCE_LEVEL=(\d+)"

        throughput_confid = re.search(pattern_throughput_confid, output)
        confidence_level = re.search(pattern_confidence_level, output)

        if throughput_confid is not None and confidence_level is not None:
            throughput_confid = float(throughput_confid.group(1))
            confidence_level = int(confidence_level.group(1))
            real_confidence = (confidence_level, throughput_confid/2)
            return real_confidence
        else:
            return (0, 0.0)

    def _parse_confidence_non_omni(self, output):
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
            elif threshold_unit_size == 'm':
                threshold_rate *= 1000*1000
            elif threshold_unit_size == 'M':
                threshold_rate *= 1024*1024
            elif threshold_unit_size == 'g':
                threshold_rate *= 1000*1000*1000
            elif threshold_unit_size == 'G':
                threshold_rate *= 1024*1024*1024
            elif threshold_unit_size == 't':
                threshold_rate *= 1000 * 1000 * 1000 * 1000
            elif threshold_unit_size == 'T':
                threshold_rate *= 1024 * 1024 * 1024 * 1024
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
            threshold_unit_type = "tps"

        return {"rate": threshold_rate,
                "unit": threshold_unit_type}

    def _parse_max_deviation(self, deviation):
        if deviation is None:
            return None
        percentual_deviation = r"(\d+(.\d+)?)\s*%"
        match = re.match(percentual_deviation, deviation)
        if match:
            return {"type": "percent",
                    "value": float(match.group(1))}
        else:
            val = self._parse_threshold(deviation)
            if val is not None:
                return {"type": "absolute",
                        "value": val}
        return None

    def _sum_results(self, first, second):
        result = {}

        #add rates
        if first["unit"] == second["unit"]:
            result["unit"] = first["unit"]
            result["rate"] = first["rate"] + second["rate"]

        # netperf measures the complete cpu utilization of the machine,
        # so both second and first should be +- the same number
        if "LOCAL_CPU_UTIL" in first and "LOCAL_CPU_UTIL" in second:
            result["LOCAL_CPU_UTIL"] = first["LOCAL_CPU_UTIL"]

        if "REMOTE_CPU_UTIL" in first and "REMOTE_CPU_UTIL" in second:
            result["REMOTE_CPU_UTIL"] = first["REMOTE_CPU_UTIL"]

        #ignoring confidence because it doesn't make sense to sum those
        return result

    def _run_server(self, cmd):
        logging.debug("running as server...")
        server = ShellProcess(cmd)
        try:
            server.wait()
        except OSError as e:
            if e.errno == errno.EINTR:
                server.kill()

    def _pretty_rate(self, rate, unit=None):
        pretty_rate = {}

        # For Request/Response tests we don't need any conversions
        if "RR" in self._testname:
            pretty_rate["unit"] = "Trans/sec"
            pretty_rate["rate"] = rate
            return pretty_rate

        # For STREAM tests we want to convert the rate from bits
        if unit is None:
            if rate < 1000:
                pretty_rate["unit"] = "bits/sec"
                pretty_rate["rate"] = rate
            elif rate < 1000 * 1000:
                pretty_rate["unit"] = "kbits/sec"
                pretty_rate["rate"] = rate / 1000
            elif rate < 1000 * 1000 * 1000:
                pretty_rate["unit"] = "mbits/sec"
                pretty_rate["rate"] = rate / (1000 * 1000)
            elif rate < 1000 * 1000 * 1000 * 1000:
                pretty_rate["unit"] = "gbits/sec"
                pretty_rate["rate"] = rate / (1000 * 1000 * 1000)
            elif rate < 1000 * 1000 * 1000 * 1000 * 1000:
                pretty_rate["unit"] = "tbits/sec"
                pretty_rate["rate"] = rate / (1000 * 1000 * 1000 * 1000)
        else:
            if unit == "bits/sec":
                pretty_rate["unit"] = "bits/sec"
                pretty_rate["rate"] = rate
            elif unit == "Kbits/sec":
                pretty_rate["unit"] = "Kbits/sec"
                pretty_rate["rate"] = rate / 1024
            elif unit == "kbits/sec":
                pretty_rate["unit"] = "kbits/sec"
                pretty_rate["rate"] = rate / 1000
            elif unit == "Mbits/sec":
                pretty_rate["unit"] = "Mbits/sec"
                pretty_rate["rate"] = rate / (1024 * 1024)
            elif unit == "mbits/sec":
                pretty_rate["unit"] = "mbits/sec"
                pretty_rate["rate"] = rate / (1000 * 1000)
            elif unit == "Gbits/sec":
                pretty_rate["unit"] = "Gbits/sec"
                pretty_rate["rate"] = rate / (1024 * 1024 * 1024)
            elif unit == "gbits/sec":
                pretty_rate["unit"] = "gbits/sec"
                pretty_rate["rate"] = rate / (1000 * 1000 * 1000)
            elif unit == "Tbits/sec":
                pretty_rate["unit"] = "Tbits/sec"
                pretty_rate["rate"] = rate / (1024 * 1024 * 1024 * 1024)
            elif unit == "tbits/sec":
                pretty_rate["unit"] = "tbits/sec"
                pretty_rate["rate"] = rate / (1000 * 1000 * 1000 * 1000)

        return pretty_rate

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
            clients = []
            client_results = []
            for i in range(0, self._num_parallel):
                clients.append(ShellProcess(cmd))

            for client in clients:
                ret_code = None
                try:
                    ret_code = client.wait()
                    rv += ret_code
                except OSError as e:
                    if e.errno == errno.EINTR:
                        client.kill()

                output = client.read_nonblocking()
                logging.debug(output)

                if ret_code is not None and ret_code == 0:
                    client_results.append(self._parse_output(output))

            if len(client_results) > 0:
                #accumulate all the parallel results into one
                result = client_results[0]
                for res in client_results[1:]:
                    result = self._sum_results(result, res)

                results.append(result)
                rates.append(results[-1]["rate"])

        if results > 1:
            res_data["results"] = results

        if len(rates) > 0:
            rate = sum(rates)/len(rates)
        else:
            rate = 0.0

        if len(rates) > 1:
            # setting deviation to 2xstd_deviation because of the 68-95-99.7
            # rule this seems comparable to the -I 99 netperf setting
            res_data["std_deviation"] = std_deviation(rates)
            rate_deviation = 2*res_data["std_deviation"]
        elif len(rates) == 1 and self._confidence is not None:
            result = results[0]
            rate_deviation = rate * (result["confidence"][1] / 100)
        else:
            rate_deviation = 0.0

        res_data["rate"] = rate
        res_data["rate_deviation"] = rate_deviation

        rate_pretty = self._pretty_rate(rate)
        rate_dev_pretty = self._pretty_rate(rate_deviation, unit=rate_pretty["unit"])

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

        res_val = False
        res_data["msg"] = "Measured rate was %.2f +-%.2f %s" %\
                                            (rate_pretty["rate"],
                                             rate_dev_pretty["rate"],
                                             rate_pretty["unit"])
        if rate > 0.0:
            res_val = True
        else:
            res_val = False
            return (res_val, res_data)

        if self._max_deviation is not None:
            if self._max_deviation["type"] == "percent":
                percentual_deviation = (rate_deviation / rate) * 100
                if percentual_deviation > self._max_deviation["value"]:
                    res_val = False
                    res_data["msg"] = "Measured rate %.2f +-%.2f %s has bigger "\
                                      "deviation than allowed (+-%.2f %%)" %\
                                      (rate_pretty["rate"],
                                       rate_dev_pretty["rate"],
                                       rate_pretty["unit"],
                                       self._max_deviation["value"])
                    return (res_val, res_data)
            elif self._max_deviation["type"] == "absolute":
                if rate_deviation > self._max_deviation["value"]["rate"]:
                    pretty_deviation = self._pretty_rate(self._max_deviation["value"]["rate"])
                    res_val = False
                    res_data["msg"] = "Measured rate %.2f +-%.2f %s has bigger "\
                                      "deviation than allowed (+-%.2f %s)" %\
                                      (rate_pretty["rate"],
                                       rate_dev_pretty["rate"],
                                       rate_pretty["unit"],
                                       pretty_deviation["rate"],
                                       pretty_deviation["unit"])
                    return (res_val, res_data)
        if self._threshold_interval is not None:
            result_interval = (rate - rate_deviation,
                               rate + rate_deviation)

            threshold_pretty = self._pretty_rate(self._threshold["rate"])
            threshold_dev_pretty = self._pretty_rate(self._threshold_deviation["rate"],
                                                     unit = threshold_pretty["unit"])

            if self._threshold_interval[0] > result_interval[1]:
                res_val = False
                res_data["msg"] = "Measured rate %.2f +-%.2f %s is lower "\
                                  "than threshold %.2f +-%.2f %s" %\
                                  (rate_pretty["rate"],
                                   rate_dev_pretty["rate"],
                                   rate_pretty["unit"],
                                   threshold_pretty["rate"],
                                   threshold_dev_pretty["rate"],
                                   threshold_pretty["unit"])
                return (res_val, res_data)
            else:
                res_val = True
                res_data["msg"] = "Measured rate %.2f +-%.2f %s is higher "\
                                  "than threshold %.2f +-%.2f %s" %\
                                  (rate_pretty["rate"],
                                   rate_dev_pretty["rate"],
                                   rate_pretty["unit"],
                                   threshold_pretty["rate"],
                                   threshold_dev_pretty["rate"],
                                   threshold_pretty["unit"])
                return (res_val, res_data)
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
