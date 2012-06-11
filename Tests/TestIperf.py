"""
This module defines iperf test
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import logging
from Common.TestsCommon import TestGeneric
from Common.ExecCmd import exec_cmd
from Common.ShellProcess import ShellProcess
import time
import errno
import re

class TestIperf(TestGeneric):
    def _install_iperf(self):
        # by default dies on failure
        logging.info("trace: _install_iperf")
        exec_cmd("wget -P %s/ %s" % (self._temp_dir, self._harness_url) )
        exec_cmd("cd %s; tar -xvzf %s" % (self._temp_dir, self._harness_archive))
        exec_cmd("cd %s/%s; ./configure; make; " % (self._temp_dir, self._harness))

    def _compose_iperf_cmd(self, role):
        iperf_options = self.get_opt("iperf_opts")
        if iperf_options is None:
            iperf_options = ""

        cmd = ""
        if role == "client":
            iperf_server = self.get_mopt("iperf_server", opt_type="addr")
            cmd = "cd %s/%s/src; ./iperf --%s %s -t %s %s" % (self._temp_dir, self._harness, role, iperf_server, self.duration, iperf_options)
        elif role == "server":
            bind = self.get_opt("bind", opt_type="addr")
            cmd = "cd %s/%s/src; ./iperf --%s -B %s %s" % (self._temp_dir, self._harness, role, bind, iperf_options)

        return cmd

    def _rate_over_threshold(self, rate):
        # convert rate to the same unit as threshold unit
        pattern = "(\d*(\.\d*){0,1})\s*([ kMGT])bits\/sec"

        # parse threshold value
        r1 = re.match(pattern, self.threshold)
        thr_units = r1.group(3)

        # parse measured rate value
        r2 = re.match(pattern, rate)
        rate_units = r2.group(3)

        thr_val = float(r1.group(1))

        rate_val = float(r2.group(1))

        # do the conversion of rate units
        if thr_units != rate_units:
            # remove any k,M,G,T from measured rate
            if rate_units == 'k':
                rate_val *= 1000
            elif rate_units == 'M':
                rate_val *= 1000*1000
            elif rate_val == 'G':
                rate_val *= 1000*1000*1000

            # divide by k or M or G if present
            if thr_units == 'k':
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
        if self.threshold is not None:
            # check if expected threshold is reached
            m = re.search("\[[^0-9]*[0-9]*\]\s*0.0-\d*\.\d sec\s*\d*(\.\d*){0,1}\s*[ kGMT]Bytes\s*(\d*(\.\d*){0,1}\s*[ kGMT]bits\/sec)", output)
            if m is None:
                logging.info("Could not get performance throughput!")
                return False

            rate = m.group(2)
            return self._rate_over_threshold(rate)

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
        self._harness = "iperf-2.0.5"
        self._harness_archive = self._harness + ".tar.gz"
        self._harness_url = "http://sourceforge.net/projects/iperf/files/%s/download" % self._harness_archive

        self.duration = self.get_opt("duration")
        if self.duration is None:
            self.duration = 60    # for client purposes
        else:
            self._keep_server_running = False    # for server purposes

        # same for client and server
        installed = self.get_opt("install_dir")
        if installed is None:
            self._temp_dir = (exec_cmd("mktemp -d")[0]).strip()
            self._install_iperf()
        else:
            self._temp_dir = installed

        self.threshold = self.get_opt("threshold")

        role = self.get_mopt("role")
        cmd = self._compose_iperf_cmd(role)
        logging.debug("compiled command: %s" % cmd)

        if role == "server":
            logging.debug("running as server ...")
            self.run_server(cmd)
        elif role == "client":
            logging.debug("running as client ...")
            rv = self.run_client(cmd)
            if rv == False:
                return self.set_fail("iperf test failed, measured rate is below expected threshold")

        return self.set_pass()
