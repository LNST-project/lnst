import logging
import subprocess
import json
from json.decoder import JSONDecodeError
from lnst.Common.Parameters import (
    IntParam,
    IpParam,
    StrParam,
    BoolParam,
    ListParam
)
from lnst.Common.Parameters import HostnameOrIpParam
from lnst.Common.Utils import is_installed
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError


class IperfBase(BaseTestModule):
    mptcp = BoolParam(default=False)

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
            stdout = stdout.decode()
            stderr = stderr.decode()
        except KeyboardInterrupt:
            pass

        try:
            self._res_data["data"] = json.loads(stdout)
        except JSONDecodeError:
            self._res_data["msg"] = "Error while parsing the iperf json output"
            self._res_data["data"] = stdout
            self._res_data["stderr"] = stderr
            logging.error(self._res_data["msg"])
            return False

        try:
            self._check_json_sanity()
        except:
            self._res_data["msg"] = "Iperf provided incomplete json data"
            self._res_data["data"] = stdout
            self._res_data["stderr"] = stderr
            logging.error(self._res_data["msg"])
            return False

        self._res_data["stderr"] = stderr

        if stderr != "":
            self._res_data["msg"] = "errors reported by iperf"
            logging.error(self._res_data["msg"])
            logging.error(self._res_data["stderr"])

        if server.returncode > 0:
            self._res_data["msg"] = "{} returncode = {}".format(
                    self._role, server.returncode)
            logging.error(self._res_data["msg"])
            return False

        return True

    def _check_json_sanity(self):
        data = self._res_data["data"]
        if "start" not in data:
            raise Exception()

        if "end" not in data:
            raise Exception()

        if len(data["intervals"]) == 0:
            raise Exception()

        if "streams" not in data["end"]:
            raise Exception


class IperfServer(IperfBase):
    bind = IpParam()
    port = IntParam()
    cpu_bind = ListParam(type=IntParam())
    opts = StrParam()
    oneoff = BoolParam(default=False)

    _role = "server"
    def _compose_cmd(self):
        bind = ""
        port = ""
        oneoff = ""

        if "bind" in self.params:
            bind = "-B {}".format(self.params.bind)

        if "port" in self.params:
            port = "-p {}".format(self.params.port)

        if "cpu_bind" in self.params and len(self.params.cpu_bind):
            cpu = "taskset -c " + ','.join(str(cpu) for cpu in self.params.cpu_bind)
        else:
            cpu = ""

        if "oneoff" in self.params and self.params.oneoff:
            oneoff = "-1"

        mptcp = "--multipath" if self.params.mptcp else ""

        cmd = "{cpu} iperf3 -s {bind} -J {port} {oneoff} {mptcp} {opts}".format(
                cpu=cpu,
                bind=bind, port=port, oneoff=oneoff, mptcp=mptcp,
                opts=self.params.opts if "opts" in self.params else "")

        return cmd


class IperfClient(IperfBase):
    server = HostnameOrIpParam(mandatory=True)
    duration = IntParam(default=10)
    warmup_duration = IntParam(default=0, mandatory=False)
    udp = BoolParam(default=False)
    sctp = BoolParam(default=False)
    port = IntParam()
    client_port = IntParam()
    blksize = IntParam()
    mss = IntParam()
    cpu_bind = ListParam(type=IntParam())
    parallel = IntParam()
    opts = StrParam()

    _role = "client"

    def __init__(self, **kwargs):
        super(IperfClient, self).__init__(**kwargs)

        if self.params.udp and self.params.sctp:
            raise TestModuleError("Parameters udp and sctp are mutually exclusive!")

    def runtime_estimate(self):
        _duration_overhead = 5
        return self.params.duration + self.params.warmup_duration * 2 + _duration_overhead

    def _compose_cmd(self):
        port = ""

        if "port" in self.params:
            port = "-p {:d}".format(self.params.port)

        if "client_port" in self.params:
            client_port = "--cport {:d}".format(self.params.client_port)

        if "blksize" in self.params:
            blksize = "-l {:d}".format(self.params.blksize)
        else:
            blksize = ""

        if "mss" in self.params:
            mss = "-M {:d}".format(self.params.mss)
        else:
            mss = ""

        if "cpu_bind" in self.params and len(self.params.cpu_bind):
            cpu = "taskset -c " + ','.join(str(cpu) for cpu in self.params.cpu_bind)
        else:
            cpu = ""


        if "parallel" in self.params:
            parallel = "-P {:d}".format(self.params.parallel)
        else:
            parallel = ""

        if self.params.udp:
            test = "--udp"
        elif self.params.sctp:
            test = "--sctp"
        elif self.params.mptcp:
            test = "--multipath"
        else:
            test = ""

        duration = self.params.duration + self.params.warmup_duration * 2  # *2 to add warm up and warm down durations
        logging.debug(f"Measuring for {duration} seconds (perf_duration + perf_warmup_duration * 2).")

        cmd = ("{cpu} iperf3 -c {server} -b 0/1000 -J -t {duration}"
               " {test} {mss} {blksize} {parallel} {port} {client_port}"
               " {opts}".format(
                cpu=cpu,
                server=self.params.server, duration=duration,
                test=test, mss=mss, blksize=blksize,
                parallel=parallel,
                port=port,
                client_port=client_port,
                opts=self.params.opts if "opts" in self.params else ""))

        return cmd
