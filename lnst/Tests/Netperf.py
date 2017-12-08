import logging
import errno
import re
import signal
import time
import subprocess
from lnst.Common.Parameters import IntParam, IpParam, StrParam, Param
from lnst.Common.TestModule import BaseTestModule, TestModuleError
from lnst.Common.ShellProcess import ShellProcess
from lnst.Common.Utils import is_installed, std_deviation


class Netserver(BaseTestModule):
    bind = IpParam(mandatory=True)
    port = IntParam()
    opts = StrParam()

    def wait_on_interrupt(self):
        try:
            handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, signal.default_int_handler)
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            signal.signal(signal.SIGINT, handler)

    def run(self):
        if not is_installed("netserver"):
            res_data = {}
            res_data["msg"] = "Netserver is not installed on this machine!"
            logging.error(res_data["msg"])
            self._res_data = res_data
            return False

        cmd = "netserver -D{bind}{port} {opts}".format(
                bind = " -L " + str(self.params.bind),
                port = " -p " + str(self.params.port) if "port" in self.params
                                                      else "",
                opts = self.params.opts if "opts" in self.params else "")

        logging.debug("compiled command: %s" % cmd)

        logging.debug("running as server...")

        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, close_fds=True)

        self.wait_on_interrupt()

        proc.kill()

        return True

class Netperf(BaseTestModule):
    _nonomni_tests = ["SCTP_STREAM", "SCTP_STREAM_MANY", "SCTP_RR"]
    _omni_tests = ["TCP_STREAM", "TCP_RR", "UDP_STREAM", "UDP_RR"]

    _supported_tests = _nonomni_tests + _omni_tests

    server = IpParam(mandatory=True)
    testname = StrParam(mandatory=True)
    duration = IntParam(mandatory=True)

    bind = IpParam()
    port = IntParam()
    testoptions = StrParam()
    confidence = StrParam()
    cpu_util = StrParam()
    num_parallel = IntParam(default=1)
    runs = IntParam(default=1)
    debug = IntParam(default=0)
    opts = StrParam()

    max_deviation = Param()

    threshold = Param()
    threshold_deviation = Param()
    threshold_interval = Param()

    def __init__(self, **kwargs):
        super(Netperf, self).__init__(**kwargs)

        if self.params.testname not in self._supported_tests:
            supported_tests = ', '.join(self._supported_tests)
            logging.warning("Only %s tests are now officialy supported "
                    "by LNST. You can use other tests, but test result may not "
                    "be correct." % supported_tests)

        if "confidence" in self.params:
            tmp = self.params.confidence.split(",")
            if tmp[0] not in ["99", "95"]:
                raise TestModuleError("Confidence level must be 95 or 99.")
            try:
                int(tmp[1])
            except ValueError:
                raise TestModuleError("Confidence interval must be an integer.")

        if "cpu_util" in self.params:
            if self.params.cpu_util not in ["both", "local", "remote"]:
                raise TestModuleError("cpu_util can be 'both', 'local' or 'remote'")



        if "threshold_deviation" in self.params:
            self._check_threshold_param(self.params.threshold_deviation,
                                        "threshold_deviation")

        else:
            self.params.threshold_deviation = {"rate": 0.0,
                                               "unit": "bps"}


        if "threshold" in self.params:
            self._check_threshold_param(self.params.threshold,
                                        "threshold")

            rate = self.params.threshold["rate"]
            deviation = self.params.threshold_deviation["rate"]
            self.params.threshold_interval = (rate - deviation,
                                              rate + deviation)

        if "max_deviation" in self.params:
            if not isinstance(self.params.max_deviation, dict):
                raise TestModuleError("max_deviation is expected to be dictionary")

            if 'type' not in self.params.max_deviation:
                raise TestModuleError("max_deviation 'type' has to be specified ('percent' or 'absolute')")

            if self.params.max_deviation['type'] not in ['percent', 'absolute']:
                raise TestModuleError("max_deviation 'type' can be 'percent' or 'absolute'")



            if self.params.max_deviation['type'] is 'percent':
                if 'value' not in self.params.max_deviation:
                    raise TestModuleError("max_deviation 'value' has to be specified")

                self.params.max_deviation['value'] = float(self.params.max_deviation['value'])

            if self.params.max_deviation['type'] is 'absolute':
                if not isinstance(self.params.max_deviation, dict):
                    raise TestModuleError("max_deviation 'value' is expected to be dictionary for 'absolute' type")

                self.params.max_deviation['value'] = self._parse_threshold(self.params.max_deviation['value'],
                                            "max_deviation 'value'")


    def _check_threshold_param(self, threshold, name):
            if not isinstance(threshold, dict):
                raise TestModuleError("%s is expected to be dictionary", name)

            if 'rate' not in threshold:
                raise TestModuleError("%s expects 'rate' key in dictionary", name)

            threshold['rate'] = float(threshold['rate'])

            if 'unit' not in threshold:
                raise TestModuleError("%s expects 'unit' key in dictionary", name)

            if self.params.testname in ["TCP_STREAM", "UDP_STREAM",
                                        "SCTP_STREAM", "SCTP_STREAM_MANY"]:
                if threshold['unit'] is not 'bps':
                    raise TestModuleError("unit can be 'bps' for STREAMs")
            else:
                if threshold['unit'] is not ['tps']:
                    raise TestModuleError("unit can be 'tps' for RRs")


    def _is_omni(self):
        return self.params.testname in self._omni_tests

    def _compose_cmd(self):
        """
        composes commands for netperf and netserver based on xml recipe
        """
        cmd = "netperf -H %s -f k" % self.params.server
        if self._is_omni():
            # -P 0 disables banner header of output
            cmd += " -P 0"
        if "bind" in self.params:
            """
            application is bound to this address
            """
            cmd += " -L %s" % self.params.bind
        if "port" in self.params:
            """
            client connects on this port
            """
            cmd += " -p %s" % self.params.port
        if "duration" in self.params:
            """
            test will last this duration
            """
            cmd += " -l %s" % self.params.duration
        if "testname" in self.params:
            """
            test that will be performed
            """
            cmd += " -t %s" % self.params.testname

        if "confidence" in self.params and self.params.num_parallel <= 1:
            """
            confidence level that Netperf should try to achieve
            """
            cmd += " -I %s" % self.params.confidence
            if self.params.runs >= 3:
                cmd += " -i %d,%d" % (self.params.runs, self.params.runs)
                self.params.runs = 1

        if "cpu_util" in self.params:
            if self.params.cpu_util.lower() == "both":
                cmd += " -c -C"
            elif self.params.cpu_util.lower() == "local":
                cmd += " -c"
            elif self.params.cpu_util.lower() == "remote":
                cmd += " -C"

        if self.params.debug > 0:
            cmd += " -%s" % ('d' * self.params.debug)

        if "netperf_opts" in self.params:
            """
            custom options for netperf
            """
            cmd += " %s" % self.params.netperf_opts

        if self.params.num_parallel > 1:
            """
            wait 1 second before starting the data transfer
            taken from the super_netperf script, can be removed if it
            doesn't make sense
            """
            cmd += " -s 1"

        # Print only relevant output
        if self._is_omni():
            cmd += ' -- -k "THROUGHPUT, LOCAL_CPU_UTIL, REMOTE_CPU_UTIL, CONFIDENCE_LEVEL, THROUGHPUT_CONFID"'

        if "testoptions" in self.params:
            if self._is_omni():
                cmd += " %s" % self.params.testoptions
            else:
                cmd += " -- %s" % self.params.testoptions

        return cmd

    def _parse_output(self, output):
        res_val = None

        if self._is_omni():
            res_val = self._parse_omni_output(output)
        else:
            res_val = self._parse_non_omni_output(output)

        if "confidence" in self.params:
            confidence = self._parse_confidence(output)
            res_val["confidence"] = confidence

        return res_val

    def _parse_omni_output(self, output):
        res_val = {}

        pattern_throughput = "THROUGHPUT=(\d+\.\d+)"
        throughput = re.search(pattern_throughput, output)

        if throughput is None:
            rate_in_kb = 0.0
        else:
            rate_in_kb = float(throughput.group(1))

        res_val["rate"] = rate_in_kb*1000
        res_val["unit"] = "bps"

        if "cpu_util" in self.params:
            if self.params.cpu_util == "local" or self.params.cpu_util == "both":
                pattern_loc_cpu_util = "LOCAL_CPU_UTIL=([-]?\d+\.\d+)"
                loc_cpu_util = re.search(pattern_loc_cpu_util, output)
                res_val["LOCAL_CPU_UTIL"] = float(loc_cpu_util.group(1))

            if self.params.cpu_util == "remote" or self.params.cpu_util == "both":
                pattern_rem_cpu_util = "REMOTE_CPU_UTIL=([-]?\d+\.\d+)"
                rem_cpu_util = re.search(pattern_rem_cpu_util, output)
                res_val["REMOTE_CPU_UTIL"] = float(rem_cpu_util.group(1))

        return res_val

    def _parse_non_omni_output(self, output):
        res_val = {}

        # pattern for SCTP streams and other tests
        # decimal decimal decimal float (float)
        pattern = "\d+\s+\d+\s+\d+\s+\d+\.\d+\s+(\d+(?:\.\d+){0,1})"
        if "cpu_util" in self.params:
            # cpu utilization data in format: float float
            pattern += "\s+(\d+(?:\.\d+){0,1})\s+(\d+(?:\.\d+){0,1})"

        r2 = re.search(pattern, output.lower())

        if r2 is None:
            rate_in_kb = 0.0
        else:
            rate_in_kb = float(r2.group(1))
            if "cpu_util" in self.params:
                res_val["LOCAL_CPU_UTIL"] = float(r2.group(2))
                res_val["REMOTE_CPU_UTIL"] = float(r2.group(3))

        res_val["rate"] = rate_in_kb*1000
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

    def _pretty_rate(self, rate, unit=None):
        pretty_rate = {}
        if unit is None:
            if rate < 1000:
                pretty_rate["unit"] = "bits/sec"
                pretty_rate["rate"] = rate
            elif rate < 1000**2:
                pretty_rate["unit"] = "kbits/sec"
                pretty_rate["rate"] = rate / 1000
            elif rate < 1000**3:
                pretty_rate["unit"] = "mbits/sec"
                pretty_rate["rate"] = rate / (1000**2)
            elif rate < 1000**4:
                pretty_rate["unit"] = "gbits/sec"
                pretty_rate["rate"] = rate / (1000**3)
            elif rate < 1000**5:
                pretty_rate["unit"] = "tbits/sec"
                pretty_rate["rate"] = rate / (1000**4)
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
                pretty_rate["rate"] = rate / (1024**2)
            elif unit == "mbits/sec":
                pretty_rate["unit"] = "mbits/sec"
                pretty_rate["rate"] = rate / (1000**2)
            elif unit == "Gbits/sec":
                pretty_rate["unit"] = "Gbits/sec"
                pretty_rate["rate"] = rate / (1024**3)
            elif unit == "gbits/sec":
                pretty_rate["unit"] = "gbits/sec"
                pretty_rate["rate"] = rate / (1000**3)
            elif unit == "Tbits/sec":
                pretty_rate["unit"] = "Tbits/sec"
                pretty_rate["rate"] = rate / (1024**4)
            elif unit == "tbits/sec":
                pretty_rate["unit"] = "tbits/sec"
                pretty_rate["rate"] = rate / (1000**4)

        return pretty_rate

    def _run_client(self, cmd):
        logging.debug("running as client...")

        res_data = {}
        res_data["testname"] = self.params.testname

        rv = 0
        results = []
        rates = []
        for i in range(1, self.params.runs+1):
            if self.params.runs > 1:
                logging.info("Netperf starting run %d" % i)
            clients = []
            client_results = []
            for i in range(0, self.params.num_parallel):
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
        elif len(rates) == 1 and "confidence" in self.params:
            result = results[0]
            rate_deviation = rate * (result["confidence"][1] / 100)
        else:
            rate_deviation = 0.0

        res_data["rate"] = rate
        res_data["rate_deviation"] = rate_deviation

        rate_pretty = self._pretty_rate(rate)
        rate_dev_pretty = self._pretty_rate(rate_deviation, unit=rate_pretty["unit"])

        if rv != 0 and self.params.runs == 1:
            res_data["msg"] = "Could not get performance throughput!"
            logging.info(res_data["msg"])
            return (False, res_data)
        elif rv != 0 and self.params.runs > 1:
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

        if "max_deviation" in self.params:
            if self.params.max_deviation["type"] == "percent":
                percentual_deviation = (rate_deviation / rate) * 100
                if percentual_deviation > self.params.max_deviation["value"]:
                    res_val = False
                    res_data["msg"] = "Measured rate %.2f +-%.2f %s has bigger "\
                                      "deviation than allowed (+-%.2f %%)" %\
                                      (rate_pretty["rate"],
                                       rate_dev_pretty["rate"],
                                       rate_pretty["unit"],
                                       self.params.max_deviation["value"])
                    return (res_val, res_data)
            elif self.params.max_deviation["type"] == "absolute":
                if rate_deviation > self.params.max_deviation["value"]["rate"]:
                    pretty_deviation = self._pretty_rate(self.params.max_deviation["value"]["rate"])
                    res_val = False
                    res_data["msg"] = "Measured rate %.2f +-%.2f %s has bigger "\
                                      "deviation than allowed (+-%.2f %s)" %\
                                      (rate_pretty["rate"],
                                       rate_dev_pretty["rate"],
                                       rate_pretty["unit"],
                                       pretty_deviation["rate"],
                                       pretty_deviation["unit"])
                    return (res_val, res_data)
        if "threshold_interval" in self.params:
            result_interval = (rate - rate_deviation,
                               rate + rate_deviation)

            threshold_pretty = self._pretty_rate(self.params.threshold["rate"])
            threshold_dev_pretty = self._pretty_rate(self.params.threshold_deviation["rate"],
                                                     unit = threshold_pretty["unit"])

            if self.params.threshold_interval[0] > result_interval[1]:
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
        if not is_installed("netperf"):
            res_data = {}
            res_data["msg"] = "Netperf is not installed on this machine!"
            logging.error(res_data["msg"])
            self._res_data = res_data
            return False

        (rv, res_data) = self._run_client(cmd)
        self._res_data = res_data
        if rv is False:
            return False
        return True
