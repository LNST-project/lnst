from abc import ABC, abstractmethod
import logging

from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError
from lnst.Common.Parameters import BoolParam, IntParam, IpParam, ListParam, StrParam
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.Utils import is_installed


class RDMABandwidthBase(ABC, BaseTestModule):
    """
    RDMA / InfiniBand bandwidth test using `ib_send_bw`
    """
    device_name = StrParam(mandatory=True)
    duration = IntParam()
    port = IntParam()
    cpu_bind = ListParam(type=IntParam())
    size = IntParam(default=65536)

    def run(self) -> bool:
        self._res_data = {}
        if not is_installed("ib_send_bw"):
            self._res_data["msg"] = "perftest package (providing ib_send_bw) is not installed on this machine!"
            logging.error(self._res_data["msg"])
            return False

        command = self._compose_cmd()
        logging.debug(command)
        out, _ = exec_cmd(command)

        filtered_lines = [line for line in out.split("\n") if line.strip() and line.find("WARNING:") == -1]
        if len(filtered_lines) > 1:
            raise TestModuleError(f"{self.__class__.__name__}: Expecting one line in the output")

        bandwidth = float(filtered_lines[0].strip())

        self._res_data["bandwidth"] = bandwidth
        return True

    def _compose_cmd(self) -> str:
        command = self._compose_base_cmd()
        command += " --output bandwidth"
        command += " --rdma_cm"  # required for siw, optional for rxe
        command += f" --ib-dev {self.params.device_name}"
        command += f" --size {self.params.size}"

        if "duration" in self.params:
            command += f" --duration {self.params.duration}"

        if "port" in self.params:
            command += f" --port {self.params.port}"

        if "opts" in self.params:
            command += f" {self.params.opts}"

        if "cpu_bind" in self.params and self.params.cpu_bind:
            prefix = "taskset -c " + ",".join(map(str, self.params.cpu_bind))
            command = f"{prefix} {command}"

        return command

    @abstractmethod
    def _compose_base_cmd(self) -> str:
        ...


class RDMABandwidthServer(RDMABandwidthBase):
    def _compose_base_cmd(self) -> str:
        return "ib_send_bw"


class RDMABandwidthClient(RDMABandwidthBase):
    dst_ip = IpParam(mandatory=True)
    src_ip = IpParam(mandatory=True)
    mtu = IntParam()
    perform_warmup = BoolParam(default=False)

    def _compose_base_cmd(self) -> str:
        command = (
            f"ib_send_bw {self.params.dst_ip}"
            f" --source_ip {self.params.src_ip}"
        )

        if "mtu" in self.params:
            command += f" --mtu {self.params.mtu}"

        if self.params.perform_warmup:
            command += " --perform_warm_up"

        return command
