import re
import os
import logging
import subprocess
import signal
import tempfile
from lnst.Common.Parameters import (
    StrParam,
    ListParam,
    DeviceParam,
    BoolParam,
)
from lnst.Common.Utils import is_installed
from lnst.Tests.BaseTestModule import BaseTestModule


class PacketAssert(BaseTestModule):
    interface = DeviceParam(mandatory=True)
    p_filter = StrParam(default="")
    grep_for = ListParam(default=[])
    promiscuous = BoolParam(default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._grep_exprs = []
        self._p_recv = 0

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
        cmd += ' -nn -U -i %s "%s"' % (iface, filt)

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

        with tempfile.TemporaryDirectory() as tmpdir:
            stdout_path = os.path.join(tmpdir, "stdout")
            stderr_path = os.path.join(tmpdir, "stderr")
            with (
                open(stdout_path, "wb") as stdout_file,
                open(stderr_path, "wb") as stderr_file,
            ):
                # tcpdump itself handles SIGINT by flushing its output and
                # exiting. The capture output is stored in files and read only
                # after tcpdump exits, so nothing that was already printed can
                # be lost when the capture is stopped.
                old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
                try:
                    packet_assert_process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        close_fds=True,
                    )
                    packet_assert_process.wait()
                finally:
                    signal.signal(signal.SIGINT, old_handler)

            with open(stdout_path, "rb") as stdout_file:
                stdout = stdout_file.read().decode()
            with open(stderr_path, "rb") as stderr_file:
                stderr = stderr_file.read().decode()

        self._res_data["stderr"] = stderr
        self._res_data["stdout"] = stdout
        # tcpdump always reports information to stderr, there may be actual
        # errors but also just generic debug information
        logging.debug(self._res_data["stderr"])
        logging.debug(self._res_data["stdout"])

        for line in stdout.split("\n"):
            self._check_line(line)

        logging.debug("Capturing finised. Received %d packets." % self._p_recv)
        self._res_data["p_recv"] = self._p_recv

        if packet_assert_process.returncode != 0:
            return False
        else:
            return True
