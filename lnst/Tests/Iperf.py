import logging
import signal
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
        except KeyboardInterrupt:
            server.send_signal(signal.SIGINT)
        finally:
            stdout, stderr = server.communicate()
            stdout = stdout.decode().strip()
            stderr = stderr.decode().strip()

        if server.returncode > 0:
            msg = f"iperf {self._role} returncode = {server.returncode}"
            logging.error(msg)
            logging.error(f"iperf stderr: {stderr}")
            logging.debug(f"iperf stdout: {stdout}")
            self._res_data["msg"] = msg
            self._res_data["stderr"] = stderr
            return False

        try:
            self._res_data["data"] = json.loads(stdout)
        except JSONDecodeError:
            msg = "Error while parsing the iperf json output"
            logging.error(msg)
            logging.error(f"iperf stderr: {stderr}")
            logging.debug(f"iperf stdout: {stdout}")
            self._res_data["msg"] = msg
            self._res_data["stderr"] = stderr
            return False

        if not self._is_json_complete(self._res_data["data"]):
            msg = "Iperf provided incomplete json data"
            logging.error(msg)
            logging.error(f"iperf stderr: {stderr}")
            logging.debug(f"iperf stdout: {stdout}")
            self._res_data["msg"] = msg
            self._res_data["stderr"] = stderr
            return False

        return True

    @staticmethod
    def _is_json_complete(data: dict) -> bool:
        return (
            "start" in data
            and "end" in data
            and len(data["intervals"]) > 0
            and "streams" in data["end"]
        )


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
        else:
            client_port = ""

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
