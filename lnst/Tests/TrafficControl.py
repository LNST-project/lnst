import itertools
import logging
import shutil
import asyncio
import time
from typing import Iterator, Optional

from lnst.Common.Parameters import ChoiceParam, IntParam, StrParam, ListParam
from lnst.Tests.BaseTestModule import BaseTestModule


class TrafficControlRunner(BaseTestModule):
    batchfiles = ListParam(type=StrParam(), mandatory=True)
    cpu_bind = ListParam(type=IntParam())
    cpu_bind_policy = ChoiceParam(type=StrParam, choices={"all", "round-robin"}, default="round-robin")

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
        cpu_bind_gen = self._get_cpu_bind_generator()

        instances = [
            self.run_tc(tc_exec, bf, cpu_bind=next(cpu_bind_gen))
            for bf in self.params.batchfiles
        ]
        results = await asyncio.gather(*instances)
        return results

    async def run_tc(
        self,
        tc_exec: str,
        batchfile: str,
        cpu_bind: Optional[list[int]] = None,
    ) -> dict[str]:
        args = [tc_exec, "-b", batchfile]
        if cpu_bind is not None:
            args = [
                "/usr/bin/taskset",
                "-c",
                ",".join(map(str, cpu_bind)),
                *args,
            ]

        start_timestamp = time.time()
        start_time = time.perf_counter()
        logging.debug(f"Running TC: {args}")
        proc = await asyncio.create_subprocess_exec(
            *args,
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

    def _get_cpu_bind_generator(self) -> Iterator[Optional[list[int]]]:
        cpu_bind = self.params.get("cpu_bind")
        if not cpu_bind:
            return itertools.repeat(None)

        policy = self.params.cpu_bind_policy
        if policy == "round-robin":
            return ([cpu] for cpu in itertools.cycle(cpu_bind))
        return itertools.repeat(cpu_bind)
