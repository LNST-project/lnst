import csv
import logging
import os
import pathlib
import re
import subprocess
import time
import tempfile
from typing import List, Dict

from lnst.Common.Parameters import HostnameOrIpParam, StrParam, IntParam, IpParam, ChoiceParam
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError

NEPER_OUT_RE = re.compile(r"^(?P<key>.*)=(?P<value>.*)$", flags=re.M)
NEPER_PATH = pathlib.Path('/root/neper')


class NeperBase(BaseTestModule):
    _supported_workloads = set(['tcp_rr', 'tcp_crr', 'udp_rr'])
    workload = ChoiceParam(type=StrParam, choices=_supported_workloads,
                           mandatory=True)
    port = IntParam()
    control_port = IntParam()
    cpu_bind = IntParam()
    num_flows = IntParam()
    num_threads = IntParam()
    test_length = IntParam()
    request_size = IntParam()
    response_size = IntParam()
    opts = StrParam()

    def __init__(self,  **kwargs):
        self._samples_file = None
        super(NeperBase, self).__init__(**kwargs)

    def _parse_result(self, res: subprocess.CompletedProcess) -> Dict:
        data = {}
        for match in NEPER_OUT_RE.finditer(res.stdout):
            if match is not None:
                k, v = match.groups()
                if v == '':
                    v = None
                data[k] = v
        return data

    def run(self):
        self._res_data = {}
        if not NEPER_PATH.joinpath(self.params.workload).exists():
            self._res_data['msg'] = f"neper workload {self.params.workload}" \
                                    f" is not installed on this machine!"
            logging.error(self._res_data['msg'])
            return False

        with tempfile.NamedTemporaryFile('r', prefix='neper-samples-',
                                         suffix='.csv', newline='') as sf:

            cmd = self._compose_cmd(sf.name)
            logging.debug(f"compiled command: {cmd}")
            logging.debug(f"running as {self._role}")

            self._res_data["start_time"] = time.time()
            res = subprocess.run(cmd,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True, shell=True,
                                 close_fds=True, cwd=NEPER_PATH)

            if res.stderr != "":
                self._res_data["msg"] = f"errors reported by {self.params.workload}"
                logging.error(self._res_data["msg"])
                logging.error(self._res_data["stderr"])

            if res.returncode > 0:
                self._res_data["msg"] = "{} returncode = {}".format(
                    self._role, res.returncode)
                logging.error(self._res_data["msg"])
                return False

            self._res_data["data"] = self._parse_result(res)
            self._res_data["stderr"] = res.stderr
            self._res_data["samples"] = [r for r in csv.DictReader(sf)]

        return True

    def _compose_cmd(self, samples_path:str) -> str:
        cmd = [f"./{self.params.workload}",
               f"--all-samples={samples_path}"]

        if self._role == "client":
            cmd.append("-c")
        if "num_threads" in self.params:
            cmd.append(f"-T {self.params.num_threads}")
        if "num_flows" in self.params:
            cmd.append(f"-F {self.params.num_flows}")
        if "port" in self.params:
            cmd.append(f"-P {self.params.port}")
        if "control_port" in self.params:
            cmd.append(f"-C {self.params.control_port}")
        if "bind" in self.params:
            cmd.append(f"-H {self.params.bind}")
        if "server" in self.params:
             cmd.append(f"-H {self.params.server}")
        if "request_size" in self.params:
            cmd.append(f"-Q {self.params.request_size}")
        if "response_size" in self.params:
            cmd.append(f"-R {self.params.response_size}")
        if "test_length" in self.params:
            cmd.append(f"-l {self.params.test_length}")
        if "opts" in self.params:
            cmd.append(self.params.opts)

        if "cpu_bind" in self.params:
            cmd.insert(0, f"taskset -c {self.params.cpu_bind}")

        return " ".join(cmd)


class NeperServer(NeperBase):
    _role = "server"
    bind = IpParam()


class NeperClient(NeperBase):
    _role = "client"
    server = HostnameOrIpParam(mandatory=True)

    def runtime_estimate(self):
        _overhead = 5
        return self.params.test_length + _overhead
