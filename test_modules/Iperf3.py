"""
This module defines iperf3 test
"""


import logging
import time
import errno
import re
from lnst.Common.TestsCommon import TestGeneric
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.ShellProcess import ShellProcess
from lnst.Common.Utils import is_installed


class Iperf3(TestGeneric):
    def _compose_iperf_cmd(self, role):
        iperf_options = self.get_opt("iperf_opts")
        if iperf_options is None:
            iperf_options = ""

        cmd = ""
        if role == "client":
            iperf_server = self.get_mopt("iperf_server", opt_type="addr")
            cmd = "iperf3 --%s %s -t %s %s" % (role, iperf_server, self.duration, iperf_options)
        elif role == "server":
            bind = self.get_opt("bind", opt_type="addr")
            if bind != None:
                cmd = "iperf3 --%s -B %s %s" % (role, bind, iperf_options)
            else:
                cmd = "iperf3 --%s %s" % (role, iperf_options)

        return cmd

    def _rate_over_threshold(self, rate):
        # convert rate to the same unit as threshold unit
        pattern = "(\d*(\.\d*){0,1})\s*([ kKMGT])bits\/sec"

        # parse threshold value
        r1 = re.match(pattern, self.threshold)
        thr_units = r1.group(3).upper()

        # parse measured rate value
        r2 = re.match(pattern, rate)
        rate_units = r2.group(3).upper()

        thr_val = float(r1.group(1))

        rate_val = float(r2.group(1))

        # do the conversion of rate units
        if thr_units != rate_units:
            # remove any k,M,G,T from measured rate
            if rate_units == 'K':
                rate_val *= 1000
            elif rate_units == 'M':
                rate_val *= 1000*1000
            elif rate_units == 'G':
                rate_val *= 1000*1000*1000

            # divide by k or M or G if present
            if thr_units == 'K':
                rate_val /= 1000
            elif thr_units == 'M':
                rate_val /= 1000*1000
            elif thr_units == 'G':
                rate_val /= 1000*1000*1000

        if rate_val < thr_val:
            logging.info("measured rate is below threshold! " \
                         "(measured: %s < threshold: %s)" % \
                (rate, self.threshold))
            return False

        return True

    def run_client(self, cmd):
        client = ShellProcess(cmd)
        try:
            client.wait()
        except OSError as e:
            # we got interrupted, let's gather data
            if e.errno == errno.EINTR:
                client.kill()

        output = client.read_nonblocking()

        if re.search("connect failed:", output):
            logging.info("Iperf connection failed!")
            return (False, "Iperf connection failed!")

        m = re.search(" error - (.*)", output)
        if m:
            err = m.groups()[0]
            logging.info("Iperf error: %s" % err)
            return (False, "Iperf error: %s" % err)

        m = re.search(" (unrecognized option .*)", output)
        if m:
            err = m.groups()[0]
            logging.info("Iperf error: %s" % err)
            return (False, "Iperf error: %s" % err)

        m = re.search("\[[^0-9]*[0-9]*\]\s*0.0+-\s*\d*\.\d+\s*sec\s*\d*(\.\d*){0,1}\s*[ kGMT]Bytes\s*(\d*(\.\d*){0,1}\s*[ kGMT]bits\/sec)", output, re.IGNORECASE)
        if m is None:
            logging.info("Could not get performance throughput!")
            return (False, "Could not get performance throughput!")

        rate = m.group(2)
        if self.threshold is not None:
            # check if expected threshold is reached
            result = self._rate_over_threshold(rate)
            if result:
                return (True, "Measured rate (%s) is over threshold (%s)." %
                        (rate, self.threshold))
            else:
                return (False, "Measured rate (%s) is below threshold (%s)!" %
                        (rate, self.threshold))
        else:
            return True, "Measured rate: %s" % rate

    def run_server(self, cmd):
        server = ShellProcess(cmd)

        if not self._keep_server_running:
            time.sleep(float(self.duration))
            server.read_nonblocking()
            server.kill()
        else:
            try:
                server.wait()
            except OSError as e:
                if e.errno == errno.EINTR:
                     server.kill()

            server.read_nonblocking()

    def run(self):
        self._keep_server_running = True

        self.duration = self.get_opt("duration")
        if self.duration is None:
            self.duration = 60    # for client purposes
        else:
            self._keep_server_running = False    # for server purposes

        self.threshold = self.get_opt("threshold")

        role = self.get_mopt("role")
        cmd = self._compose_iperf_cmd(role)
        logging.debug("compiled command: %s" % cmd)
        if not is_installed("iperf3"):
            res_data = {}
            res_data["msg"] = "Iperf3 is not installed on this machine!"
            logging.error(res_data["msg"])
            return self.set_fail(res_data)

        if role == "server":
            logging.debug("running as server ...")
            self.run_server(cmd)

            return self.set_pass()
        elif role == "client":
            logging.debug("running as client ...")
            (rv, message) = self.run_client(cmd)
            res_data = {"msg": message}
            if rv == False:
                return self.set_fail(res_data)

            return self.set_pass(res_data)
