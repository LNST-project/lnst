import logging
import subprocess
import time
from tempfile import NamedTemporaryFile


class TrafficControlTester:
    """
    Class used as a more direct way to run tc to get better stats
    around it. Can probably be migrated into something like an
     Iperf.py, Neper.py, etc or something else.
    """

    def __init__(self, iface):
        self.iface = iface

    def run_test(self, num_rules) -> tuple[bool, float, list[str]]:

        batch = self.write_batch_file(num_rules)

        messages = []
        time_taken, res = self.run_tc(batch)
        success = res.returncode == 0
        if success:
            logging.info("TC run successful")
            messages.append(f"Successful TC run of {num_rules} took {time_taken}s")
        else:
            logging.warning("TC run failed")
            messages.append(f"Failed TC run of {num_rules} took {time_taken}")
            messages.append(res.stderr)

        return success, time_taken, messages

    def write_batch_file(self, num_rules) -> str:
        rules = self.generate_rules(num_rules)
        with NamedTemporaryFile(
                'w', suffix=".batch", prefix="tc-rules-", delete=False,
        ) as f:
            for r in rules:
                f.write(r)

        logging.info(f"tc batchfile written to {f.name}")
        return f.name

    def generate_rules(self, num_rules: int):
        """
        from https://github.com/marceloleitner/perf-flower/blob/master/rule-install-rate/run.sh
        """
        for i in range(num_rules):
            a = i & 0xff
            b = (i & 0xff00) >> 8
            c = (i & 0xff0000) >> 16
            yield f"filter add dev {self.iface} parent ffff: protocol ip prio 1 flower " \
                  f"src_mac ec:13:db:{a:02X}:{b:02X}:{c:02X} dst_mac ec:14:c2:{c:02X}:{b:02X}:{a:02X} " \
                  f"src_ip 56.{a}.{b}.{c} dst_ip 55.{c}.{b}.{a} action drop\n"

    def run_tc(self, batchfile: str) -> tuple[float, subprocess.CompletedProcess]:

        st = time.perf_counter()
        res = subprocess.run(f"tc -b {batchfile}", shell=True)
        et = time.perf_counter()

        time_taken = et - st

        return time_taken, res
