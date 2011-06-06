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

class TestIperf(TestGeneric):

    def _install_iperf(self):
        # by default dies on failure
        logging.info("trace: _install_iperf")
        self._temp_dir = (exec_cmd("mktemp -d")[0]).strip()
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

    def run_client(self, cmd):
        client = ShellProcess(cmd)
        client.wait()
        client.read_nonblocking()

    def run_server(self, cmd):
        server = ShellProcess(cmd)
        time.sleep(float(self.duration))
        server.read_nonblocking()
        server.kill()

    def run(self):
        self._harness = "iperf-2.0.5"
        self._harness_archive = self._harness + ".tar.gz"
        self._harness_url = "http://sourceforge.net/projects/iperf/files/%s/download" % self._harness_archive

        self.duration = self.get_opt("duration")
        if self.duration is None:
            self.duration = 60

        # same for client and server
        self._install_iperf()

        role = self.get_mopt("role")
        cmd = self._compose_iperf_cmd(role)
        logging.debug("compiled command: %s" % cmd)

        if role == "server":
            logging.debug("running as server ...")
            self.run_server(cmd)
        elif role == "client":
            logging.debug("running as client ...")
            self.run_client(cmd)

        return self.set_pass()
