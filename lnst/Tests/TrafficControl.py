import logging
import shutil
import asyncio
import time

from lnst.Common.Parameters import StrParam, ListParam
from lnst.Tests.BaseTestModule import BaseTestModule


class TrafficControlRunner(BaseTestModule):
    batchfiles = ListParam(type=StrParam(), mandatory=True)

    def run(self) -> bool:
        self._res_data = {}
        instance_results = asyncio.run(self.run_instances())
        all_success = all((i["success"] for i in instance_results))
        self._res_data["data"] = dict(
            instance_results=instance_results,
        )
        msgs = []
        for result in instance_results:
            if not result["success"]:
                msg = f"tc -b {result['batchfile']} failed"
                logging.warning(msg)
                logging.error(result["stderr"])
                msgs.append(msg)
                msgs.append(result["stderr"])
        self._res_data["msg"] = "\n".join(msgs)

        return all_success

    async def run_instances(self) -> list[dict]:
        tc_exec = shutil.which("tc")
        instances = [
            self.run_tc(tc_exec, bf)
            for bf in self.params.batchfiles
        ]
        results = await asyncio.gather(*instances)
        return results

    async def run_tc(self, tc_exec: str, batchfile: str) -> dict[str]:
        start_timestamp = time.time()
        start_time = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            tc_exec, "-b", batchfile,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        elapsed = time.perf_counter() - start_time
        success = proc.returncode == 0
        return dict(
            time_taken=elapsed,
            start_timestamp=start_timestamp,
            success=success,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            batchfile=batchfile,
        )
