import logging
import subprocess
import time

from lnst.Common.Parameters import StrParam
from lnst.Tests.BaseTestModule import BaseTestModule


class TrafficControlRunner(BaseTestModule):

    batchfile = StrParam(required=True)

    def run(self) -> bool:
        self._res_data = {}

        start_timestamp, time_taken, res = self.run_tc(self.params.batchfile)
        success = res.returncode == 0

        self._res_data["data"] = {
            "time_taken": time_taken,
            "start_timestamp": start_timestamp
        }

        msg = f"took {time_taken} sec"
        if success:
            self._res_data["msg"] = f"tc run successful, {msg}"
            logging.info(self._res_data["msg"])
        else:
            self._res_data["msg"] = f"tc run failed, {msg}"
            self._res_data["stderr"] = res.stderr
            logging.warning(self._res_data["msg"])
            logging.error(self._res_data["stderr"])

        return success

    def run_tc(self, batchfile: str) -> tuple[float, subprocess.CompletedProcess]:

        start_timestamp = time.time()
        st = time.perf_counter()
        res = subprocess.run(f"tc -b {batchfile}", shell=True)
        et = time.perf_counter()

        time_taken = et - st

        return start_timestamp, time_taken, res
