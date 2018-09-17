import logging
import errno
import re
import signal
import time
import subprocess
import json
from lnst.Common.Parameters import IntParam, IpParam, StrParam, Param, BoolParam
from lnst.Common.Parameters import HostnameOrIpParam
from lnst.Common.Utils import is_installed
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError

class IperfBase(BaseTestModule):
    def run(self):
        self._res_data = {}
        if not is_installed("iperf3"):
            self._res_data["msg"] = "Iperf is not installed on this machine!"
            logging.error(self._res_data["msg"])
            return False

        cmd = self._compose_cmd()

        logging.debug("compiled command: %s" % cmd)
        logging.debug("running as {} ...".format(self._role))

        server = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True)

        try:
            stdout, stderr = server.communicate()
        except KeyboardInterrupt:
            pass

        try:
            self._res_data["data"] = json.loads(stdout)
        except:
            self._res_data["data"] = stdout

        self._res_data["stderr"] = stderr

        if stderr != "":
            self._res_data["msg"] = "errors reported by iperf"
            logging.error(self._res_data["msg"])
            logging.error(self._res_data["stderr"])
            return False

        if server.returncode > 0:
            self._res_data["msg"] = "{} returncode = {}".format(
                    self._role, server.returncode)
            logging.error(self._res_data["msg"])
            return False

        return True

class IperfServer(IperfBase):
    bind = IpParam()
    port = IntParam()
    cpu_bind = IntParam()
    opts = StrParam()
    oneoff = BoolParam(default=False)

    _role = "server"
    def _compose_cmd(self):
        bind = ""
        port = ""

        if "bind" in self.params:
            bind = "-B {}".format(self.params.bind)

        if "port" in self.params:
            port = "-p {}".format(self.params.port)

        if "cpu_bind" in self.params:
            cpu = "-A {:d}".format(self.params.cpu_bind)
        else:
            cpu = ""

        if "oneoff" in self.params and self.params.oneoff:
            oneoff = "-1"

        cmd = "iperf3 -s {bind} -J {port} {cpu} {oneoff} {opts}".format(
                bind=bind, port=port, cpu=cpu, oneoff=oneoff,
                opts=self.params.opts if "opts" in self.params else "")

        return cmd


class IperfClient(IperfBase):
    server = HostnameOrIpParam(mandatory=True)
    duration = IntParam(default=10)
    udp = BoolParam(default=False)
    sctp = BoolParam(default=False)
    port = IntParam()
    blksize = IntParam()
    mss = IntParam()
    cpu_bind = IntParam()
    parallel = IntParam()
    opts = StrParam()

    _role = "client"

    def __init__(self, **kwargs):
        super(IperfClient, self).__init__(**kwargs)

        if self.params.udp and self.params.sctp:
            raise TestModuleError("Parameters udp and sctp are mutually exclusive!")

    def _compose_cmd(self):
        port = ""

        if "port" in self.params:
            port = "-p {:d}".format(self.params.port)

        if "blksize" in self.params:
            blksize = "-l {:d}".format(self.params.blksize)
        else:
            blksize = ""

        if "mss" in self.params:
            mss = "-M {:d}".format(self.params.mss)
        else:
            mss = ""

        if "cpu_bind" in self.params:
            cpu = "-A {:d}".format(self.params.cpu_bind)
        else:
            cpu = ""

        if "parallel" in self.params:
            parallel = "-P {:d}".format(self.params.parallel)

        if self.params.udp:
            test = "--udp"
        elif self.params.sctp:
            test = "--sctp"
        else:
            test = ""

        cmd = ("iperf3 -c {server} -J -t {duration}"
               " {cpu} {test} {mss} {blksize} {parallel}"
               " {opts}".format(
                server=self.params.server, duration=self.params.duration,
                cpu=cpu, test=test, mss=mss, blksize=blksize,
                parallel=parallel,
                opts=self.params.opts if "opts" in self.params else ""))

        return cmd
