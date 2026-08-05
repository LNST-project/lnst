import re
import time
import signal
import logging
from subprocess import Popen, PIPE
from threading import Thread

from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError
from lnst.Common.Parameters import StrParam, IntParam, DeviceParam, ListParam


class XDPBenchRedirectCpuOutputParser:
    def __init__(self, process: Popen):
        self._process = process
        self._raw_samples = []
        self._capturing_start = 0

    def start_sampling(self):
        thread = Thread(target=self._capture_output)
        thread.start()
        self._capturing_start = time.time()

    def _capture_output(self):
        try:
            for sample in iter(self._process.stdout.readline, ""):
                self._raw_samples.append((time.time(), sample.decode()))
        except ValueError:
            pass  # .readline raises when the xdp-bench subprocess is killed

    def parse_output(self) -> list[dict]:
        _, stderr = self._process.communicate()

        if stderr:
            logging.error(
                "xdp-bench redirect-cpu stderr:\n%s",
                stderr.decode(errors="replace"),
            )

        results = []
        blocks = self._split_into_blocks()

        for block_timestamp, block_lines in blocks:
            try:
                received, forwarded_per_cpu = self._parse_block(block_lines)
            except ValueError:
                logging.error(f"Could not parse block: {block_lines}")
                continue

            if results:
                duration = block_timestamp - (
                    results[-1]["timestamp"] + results[-1]["duration"]
                )
            else:
                duration = block_timestamp - self._capturing_start

            results.append(
                {
                    "received": received,
                    "forwarded_per_cpu": forwarded_per_cpu,
                    "duration": duration,
                    "timestamp": block_timestamp - duration,
                }
            )

        if not results:
            raise TestModuleError("Could not get xdp-bench redirect-cpu output")

        return results

    def _split_into_blocks(self) -> list[tuple[float, list[str]]]:
        blocks = []
        current_block = []
        current_timestamp = self._capturing_start

        for timestamp, line in self._raw_samples:
            if re.match(r"^\S+->", line):
                if current_block:
                    blocks.append((current_timestamp, current_block))
                current_block = [line]
                current_timestamp = timestamp
            else:
                current_block.append(line)

        if current_block:
            blocks.append((current_timestamp, current_block))

        return blocks

    def _parse_block(self, lines: list[str]) -> tuple[int, dict[int, int]]:
        """
        Parse one interval block for receive total and per-CPU kthread counts.

        Returns ``(received, forwarded_per_cpu)`` where ``forwarded_per_cpu``
        maps ``cpu_id -> pkt/s``.

        Example kthread section::

            kthread total         4,334,231 pkt/s ...
              cpu:4               2,162,754 pkt/s ...
              cpu:6               2,171,476 pkt/s ...
        """
        received = None
        forwarded_per_cpu = {}
        in_kthread_section = False

        for line in lines:
            if received is None:
                match = re.search(r"receive\s+total\s+([\d,]+)\s+pkt/s", line)
                if match:
                    received = int(match.group(1).replace(",", ""))

            if re.search(r"kthread\s+total\s+[\d,]+\s+pkt/s", line):
                in_kthread_section = True
                continue

            if in_kthread_section:
                cpu_match = re.match(r"\s+cpu:(\d+)\s+([\d,]+)\s+pkt/s", line)
                if cpu_match:
                    cpu_id = int(cpu_match.group(1))
                    pkt_s = int(cpu_match.group(2).replace(",", ""))
                    forwarded_per_cpu[cpu_id] = pkt_s
                else:
                    in_kthread_section = False

        if received is None or not forwarded_per_cpu:
            raise ValueError("Could not parse received/forwarded from block")

        return received, forwarded_per_cpu


class XDPBenchRedirectCpu(BaseTestModule):
    """
    ``xdp-bench redirect-cpu`` test module.

    Runs ``xdp-bench redirect-cpu`` on the given interface, redirecting packets
    to cpumap queues on the specified target CPUs.

    xdp-bench must be shut down with SIGINT — SIGKILL leaves the XDP program
    attached to the NIC.

    :param interface: NIC to attach XDP program to
    :param cpus: target CPU IDs for cpumap redirect (mandatory)
    :param program: ``-p`` flag — supported: ``l4-dport`` (default),
        ``l4-sport``
    :param qsize: ``-q`` flag, cpumap queue depth per CPU (default 512)
    :param remote_action: ``-r`` flag (default ``drop``)
    :param interval: stats reporting interval in seconds (default 1)
    :param duration: how long to run in seconds (default 60)
    """

    interface = DeviceParam(mandatory=True)
    cpus = ListParam(mandatory=True)
    program = StrParam(default="l4-dport")
    qsize = IntParam(default=512)
    remote_action = StrParam(default="drop")
    interval = IntParam(default=1)
    duration = IntParam(default=60, mandatory=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._res_data = []

    def run(self):
        command = self._prepare_command()
        logging.debug(f"Starting xdp-bench redirect-cpu: `{command}`")

        bench = Popen(command, stdout=PIPE, stderr=PIPE)
        output_parser = XDPBenchRedirectCpuOutputParser(bench)
        output_parser.start_sampling()
        time.sleep(self.params.duration)

        bench.send_signal(signal.SIGINT)  # must be SIGINT to detach XDP program

        self._res_data = output_parser.parse_output()
        return True

    def _prepare_command(self):
        args = ["xdp-bench", "redirect-cpu", self.params.interface.name]

        for cpu in self.params.cpus:
            args.extend(["-c", str(cpu)])

        args.extend(["-p", self.params.program])
        args.extend(["-r", self.params.remote_action])
        args.extend(["-i", str(self.params.interval)])
        args.extend(["-q", str(self.params.qsize)])
        args.append("-e")  # extended stats required for per-CPU kthread output

        return args

    def runtime_estimate(self):
        return self.params.duration + 2
