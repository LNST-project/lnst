import re
import time
import logging
from subprocess import Popen, check_output, CalledProcessError
from threading import Thread
from typing import Iterator, Union

from lnst.Common.Utils import kmod_loaded
from lnst.Common.IpAddress import Ip4Address
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError
from lnst.Common.Parameters import IntParam, IpParam, StrParam, ListParam, DeviceParam


class PktGenResultsSampler:
    def __init__(self, devs: list[str], duration: int) -> None:
        """
        PktGen output is just a table with current stats of devices. Therefore,
        each device has a separate thread that captures current status of device
        each second for `duration`.
        """
        self._devs = devs
        self._duration = duration

        self._sampling_threads: list[Thread] = []
        self._raw_samples = {}

    def start_sampling(self):
        """
        This is a separate method just to emphasize that pktgen
        needs to be started immediately after the start of sampling.
        """
        self._setup_capturing()

        for thread in self._sampling_threads:
            thread.start()

    def _setup_capturing(self):
        for device in self._devs:
            thread = Thread(target=self._read_dev_samples, args=(device,))
            self._sampling_threads.append(thread)

    def _read_dev_samples(self, device: str):
        self._raw_samples[device] = []

        for _ in range(0, self._duration + 1):  # +1 because first sample is "empty"
            with open(f"/proc/net/pktgen/{device}", "r") as file:
                self._raw_samples[device].append((time.time(), file.read()))
                # TODO: ^^^ when upgrading to python interpreter without GIL check thread safety
                # NOTE: samples are saved at it's end => the timestamp represents ending time, not the start
            time.sleep(1)

    @property
    def device_samples(self) -> dict[str, list[dict[str, Union[float, int, dict]]]]:
        for thread in self._sampling_threads:
            thread.join(timeout=2)

        samples = {}
        for device in self._devs:
            samples[device] = []
            packets_sofar = 0
            start_timestamp = self._raw_samples[device][0][0]  # first "empty" sample
            # NOTE: sample's timestamp represent the end of sampling
            # so each sample actually starts at the timestamp of previous sample

            for timestamp, raw_sample in self._raw_samples[device][
                1:
            ]:  # ignore first empty sample
                params, current = self._split_output(raw_sample)
                current = self._parse_values(current)

                packets = int(current["sofar"]) - packets_sofar

                samples[device].append(
                    {
                        "timestamp": start_timestamp,
                        "duration": timestamp - start_timestamp,
                        "packets": packets,
                        "errors": int(current["errors"]),
                        "params": params,
                    }
                )
                packets_sofar += packets
                start_timestamp = timestamp

        return samples

    def _read_dev_outputs(self) -> Iterator[tuple[str, str]]:
        for device in self._devs:
            output = ""
            with open(f"/proc/net/pktgen/{device}", "r") as f:
                output = f.readlines()
            yield device, "\n".join(output)

    def _split_output(self, output: str) -> tuple:
        match = re.search(r"Params:(.+)Current:(.+)Result:\s(?:\w+)", output, re.DOTALL)
        if not match:
            raise TestModuleError(f"Could not parse pktgen devide output: {output}")

        return match.groups()

    def _parse_values(self, params) -> dict[str, str]:
        values = {}

        for key, value in re.findall(r"(\w+):?\s(\S+)", params, re.MULTILINE):
            values[key.lower()] = value

        return values


class PktGen(BaseTestModule):
    """
    In the scope of this module, the physical interface is refered as `interface`.
    Pktgen device (interface@anything) is refered as device.

    Inspired by https://github.com/torvalds/linux/blob/master/samples/pktgen/pktgen_sample03_burst_single_flow.sh
    """

    cpus = ListParam(type=IntParam())  # each CPU is 1 generator

    src_if = DeviceParam()
    dst_mac = StrParam()

    src_ip = IpParam()
    dst_ip = IpParam()

    count = IntParam(default=0)  # 0 = no upper limit
    pkt_size = IntParam(default=60)  # 4 bytes are added for CRC by NIC
    frags = IntParam(default=1)
    burst = IntParam(default=8)

    duration = IntParam(default=60)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._devices = []

        self._res_data = {}
        self._output_parser = None

    def run(self):
        self._load_pktgen_module()
        self._pg_ctrl("reset")
        self._configure_generator()

        output_parser = PktGenResultsSampler(self._devices, self.params.duration)
        output_parser.start_sampling()

        logging.debug("Starting generator")
        pktgen = Popen("echo 'start' > /proc/net/pktgen/pgctrl", shell=True)
        # ^^ echoing start to controller is blocking => needs to be separated

        time.sleep(self.params.duration)

        pktgen.kill()  # stops pktgen

        self._res_data = output_parser.device_samples

        self._deconfigure_generator()
        return True

    def _load_pktgen_module(self):
        try:
            check_output(["/usr/sbin/modprobe", "pktgen"])
        except CalledProcessError as e:
            logging.debug(f"Modprobe of pktgen failed {e.output}")

        if not kmod_loaded("pktgen"):
            raise TestModuleError("pktgen module is not loaded")

    def _configure_generator(self):
        logging.debug("Configuring generator")

        ipv6 = True
        if isinstance(self.params.src_ip, Ip4Address):
            ipv6 = False

        src = f"src{6 if ipv6 else ''}"
        dest = f"dst{6 if ipv6 else ''}"

        for cpu in self.params.cpus:
            dev = f"{self.params.src_if.name}@{cpu}"
            logging.debug(f"Adding interface {self.params.src_if.name} to cpu {cpu}")

            self._pg_thread(cpu, f"add_device {dev}")

            self._pg_set(cpu, f"flag QUEUE_MAP_CPU")
            self._pg_set(cpu, f"count {self.params.count}")
            self._pg_set(cpu, f"pkt_size {self.params.pkt_size}")
            self._pg_set(cpu, f"flag NO_TIMESTAMP")

            self._pg_set(cpu, f"dst_mac {self.params.dst_mac}")
            self._pg_set(cpu, f"src_mac {self.params.src_if.hwaddr}")

            self._pg_set(cpu, f"{dest}_min {self.params.dst_ip}")
            self._pg_set(cpu, f"{dest}_max {self.params.dst_ip}")
            self._pg_set(cpu, f"{src}_min {self.params.src_ip}")
            self._pg_set(cpu, f"{src}_max {self.params.src_ip}")

            self._pg_set(cpu, f"burst {self.params.burst}")
            self._devices.append(dev)

    def _deconfigure_generator(self):
        logging.debug("Deconfiguring generator")
        for cpu in self.params.cpus:
            self._pg_thread(cpu, "rem_device_all")

        self._pg_ctrl("reset")

    def _pg_ctrl(self, cmd: str):
        self._write_command("/proc/net/pktgen/pgctrl", cmd)

    def _pg_thread(self, thread: int, cmd: str):
        self._write_command(f"/proc/net/pktgen/kpktgend_{thread}", cmd)

    def _pg_set(self, thread: int, cmd: str):
        self._write_command(f"/proc/net/pktgen/{self.params.src_if.name}@{thread}", cmd)

    def _write_command(self, file: str, cmd: str):
        logging.debug(f"Writing {cmd} to {file}")
        with open(file, "w") as f:
            f.write(f"{cmd}\n")

    def runtime_estimate(self):
        return self.params.duration + 5
