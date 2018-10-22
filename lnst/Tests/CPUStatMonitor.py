import re
import time
import signal
from time import sleep
from lnst.Common.Parameters import IntParam
from lnst.Tests.BaseTestModule import BaseTestModule, TestModuleError, InterruptException

def sigint_handler(signum, frame):
    raise InterruptException()

class CPUStatMonitor(BaseTestModule):
    #number of miliseconds to sleep between each sample
    interval = IntParam(default=1000)

    def run(self):
        self._res_data = {}

        raw_samples = []
        old_handler = None
        try:
            old_handler = signal.signal(signal.SIGINT, sigint_handler)
            with open("/proc/stat") as stat:
                while True:
                    stat.seek(0)
                    timestamp = time.time()
                    stat_lines = "".join(stat.readlines())
                    raw_samples.append({
                        "timestamp": timestamp,
                        "stat": stat_lines
                        })
                    sleep(self.params.interval / float(1000))
        except InterruptException:
            pass
        finally:
            if old_handler is not None:
                signal.signal(signal.SIGINT, old_handler)

        self._res_data["raw_data"] = raw_samples
        self._res_data["data"] = self._process_samples(raw_samples)

        return True

    def _process_samples(self, samples):
        result = []
        prev_sample = samples[0]
        for sample in samples[1:]:
            parsed_prev = self._parse_stat_lines(prev_sample["stat"])
            parsed_cur = self._parse_stat_lines(sample["stat"])

            interval = self._subtract_nested_dicts(parsed_cur, parsed_prev)
            interval["duration"] = (sample["timestamp"] -
                                    prev_sample["timestamp"])

            result.append(interval)

            prev_sample = sample
        return result

    def _subtract_nested_dicts(self, first, second):
        result = {}
        for key, val in first.items():
            if isinstance(val, dict):
                result[key] = self._subtract_nested_dicts(val, second[key])
            else:
                result[key] = val - second[key]
        return result

    def _parse_stat_lines(self, stat):
        result = {}
        for line in stat.split("\n"):
            cpu_data = self._parse_cpu_stats(line)
            if cpu_data:
                result[cpu_data[0]] = cpu_data[1]
                continue

            intr_data = self._parse_intr_stats(line)
            if intr_data:
                result[intr_data[0]] = intr_data[1]
                continue

            m = re.match(r"^(.*?) (\d+)$", line)
            if m:
                result[m.group(1)] = int(m.group(2))
        return result

    def _parse_cpu_stats(self, stat_line):
        result = {}
        m = re.match(r"^(cpu\d*)\s+(\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$",
                     stat_line)
        if m:
            cpu = m.group(1)
            result["user"] = int(m.group(2))
            result["nice"] = int(m.group(3))
            result["system"] = int(m.group(4))
            result["idle"] = int(m.group(5))
            result["iowait"] = int(m.group(6))
            result["irq"] = int(m.group(7))
            result["softirq"] = int(m.group(8))
            result["steal"] = int(m.group(9))
            result["guest"] = int(m.group(10))
            result["guest_nice"] = int(m.group(11))
            return cpu, result
        else:
            return None

    def _parse_intr_stats(self, stat_line):
        result = {}
        m = re.match(r"^(intr|softirq) (\d+) (.*)$", stat_line)
        if m:
            result["total"] = int(m.group(2))
            for i, irq in enumerate(m.group(3).split(" ")):
                result[i] = int(irq)
            return m.group(1), result
        else:
            return None
