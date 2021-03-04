import re
import logging
import subprocess
from lnst.Common.Parameters import StrParam, ListParam, DeviceParam, IntParam, BoolParam
from lnst.Devices.Device import Device
from lnst.Common.Utils import is_installed
from lnst.Tests.BaseTestModule import BaseTestModule
from lnst.Common.LnstError import LnstError

class PacketAssert(BaseTestModule):
    interface = DeviceParam(mandatory=True)
    p_filter = StrParam(default='')
    grep_for = ListParam(default=[])
    promiscuous = BoolParam(default=False)
    _grep_exprs = []
    _p_recv = 0

    def _prepare_grep_exprs(self):
        for expr in self.params.grep_for:
            if expr is not None:
                self._grep_exprs.append(expr)

    def _compose_cmd(self):
        cmd = "tcpdump"
        if not self.params.promiscuous:
            cmd += " -p"
        iface = self.params.interface.name
        filt = self.params.p_filter
        cmd += " -nn -i %s \"%s\"" % (iface, filt)

        return cmd

    def _check_line(self, line):
        if line != "":
            for exp in self._grep_exprs:
                if not re.search(exp, line):
                    return
            self._p_recv += 1

    def run(self):
        self._res_data = {}
        if not is_installed("tcpdump"):
            self._res_data["msg"] = "tcpdump is not installed on this machine!"
            logging.error(self._res_data["msg"])
            return False

        self._prepare_grep_exprs()
        cmd = self._compose_cmd()
        logging.debug("compiled command: {}".format(cmd))

        packet_assert_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, close_fds=True)

        try:
            self.wait_for_interrupt()
        except:
            raise LnstError("Could not handle interrupt properly.")

        stdout, stderr = packet_assert_process.communicate()
        stdout = stdout.decode()
        stderr = stderr.decode()

        self._res_data["stderr"] = stderr
        # tcpdump always reports information to stderr, there may be actual
        # errors but also just generic debug information
        logging.debug(self._res_data["stderr"])

        for line in stdout.split("\n"):
            self._check_line(line)

        logging.debug("Capturing finised. Received %d packets." % self._p_recv)
        self._res_data["p_recv"] = self._p_recv

        if packet_assert_process.returncode != 0:
            return False
        else:
            return True
