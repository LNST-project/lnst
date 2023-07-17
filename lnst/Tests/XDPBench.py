import re
import time
import signal
import logging
from subprocess import Popen, PIPE
from threading import Thread
from lnst.Devices.Device import Device

from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError
from lnst.Common.Parameters import (
    ChoiceParam,
    StrParam,
    IntParam,
    DeviceParam,
)


class XDPBenchOutputParser:
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
            pass  # .readline raises exception on killing xdp-bench subprocess

    def parse_output(self) -> list[dict]:
        _, stderr = self._process.communicate()

        logging.debug("Stderr of xdp-bench:")
        logging.debug(str(stderr))

        results = []
        previous_timestamp = self._capturing_start

        for timestamp, sample in self._raw_samples:
            try:
                rx, err = self._parse_line(sample)
            except ValueError:
                if sample:  # ignore empty lines
                    logging.error(f"Could not parse line: '{sample}'")
                continue

            duration = timestamp - previous_timestamp
            results.append(
                {"rx": rx, "err": err, "duration": duration, "timestamp": timestamp}
            )

            previous_timestamp = timestamp

        if not results:
            raise TestModuleError("Could not get xdp-bench output")

        return results

    def _parse_line(self, line: str) -> tuple:
        match = re.search(r"Summary\s+([\d,]+)\srx/s\s+([\d,]+)\serr/s?", line)

        if not match:  # skip summary line at the end + corrupted lines
            raise ValueError("Invalid line format")

        rx = match.group(1).replace(",", "")
        err = match.group(2).replace(",", "")
        # ^^ remove thousands separators

        return int(rx), int(err)


XDP_BENCH_COMMANDS = (
    "pass",
    "drop",
    "tx",
    "redirect",
    "redirect-cpu",
    "redirect-map",
    "redirect-multi",
)


class XDPBench(BaseTestModule):
    """
    xdp-bench tool abstraction. [1]

    This tool does NOT check params validity.

    xdp-bench is expected to be included in PATH env variable.

    [1] https://github.com/xdp-project/xdp-tools/
    """

    command = ChoiceParam(
        type=StrParam,
        choices=XDP_BENCH_COMMANDS,
        mandatory=True,
    )
    interface = DeviceParam(mandatory=True)
    interface2 = DeviceParam()  # used for redirect modes

    interval = IntParam(default=1)

    redirect_device = DeviceParam()
    xdp_mode = ChoiceParam(type=StrParam, choices=("native", "skb"), default="native")
    load_mode = ChoiceParam(type=StrParam, choices=("dpa", "load-bytes"))
    packet_operation = ChoiceParam(
        type=StrParam, choices=("no-touch", "read-data", "parse-ip", "swap-macs")
    )
    qsize = IntParam()
    remote_action = ChoiceParam(
        type=StrParam, choices=("disabled", "drop", "pass", "redirect")
    )

    # NOTE: order and names of params above matters. xdp-bench accepts params in that way
    duration = IntParam(default=60, mandatory=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._res_data = []

    def run(self):
        logging.debug("Starting xdp-bench")
        command = self._prepare_command()

        bench = Popen(command, stdout=PIPE)
        output_parser = XDPBenchOutputParser(bench)
        output_parser.start_sampling()
        time.sleep(self.params.duration)

        bench.send_signal(signal.SIGINT)  # needs to be shutdown gracefully

        self._res_data = output_parser.parse_output()

        return True

    def _prepare_command(self):
        return ["xdp-bench"] + self._prepare_arguments()

    def _prepare_arguments(self):
        args = []
        for param, value in self.params:
            if param == "duration":
                continue  # not a xdp-bench argument

            if param not in ("interface", "interface2", "command"):
                # ^^^ those 3 arguments are passed without arg name
                args.append(f"--{param.replace('_', '-')}")

            if isinstance(value, Device):
                value = value.name  # get if name

            args.append(str(value))

        return args

    def runtime_estimate(self):
        return self.params.duration + 2
