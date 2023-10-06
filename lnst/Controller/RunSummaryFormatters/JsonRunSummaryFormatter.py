from typing import Optional
import logging
import json

from lnst.Controller.Recipe import RecipeRun
from lnst.Controller.RecipeResults import (
    DeviceAttrSetResult,
    DeviceConfigResult,
    DeviceCreateResult,
    DeviceMethodCallResult,
    JobResult,
    JobStartResult,
    MeasurementResult,
    BaseResult,
)
from .RunSummaryFormatter import RunSummaryFormatter


class JsonRunSummaryFormatter(RunSummaryFormatter):
    def __init__(self, pretty: bool = False):
        super().__init__()
        self.pretty = pretty

    def format_run(self, run: RecipeRun) -> str:
        recipe_results = [
            transformed
            for result in run.results
            if (transformed := self._transform_result(result)) is not None
        ]

        if exc := run.exception:
            exception_result = {
                "result": "FAIL",
                "type": "exception",
                "message": str(exc),
            }
            recipe_results.append(exception_result)

        return json.dumps(
            recipe_results,
            indent=4 if self.pretty else None,
        )

    def _transform_result(self, result: BaseResult) -> Optional[dict]:
        ret = {
            "result": str(result.result),
        }
        if isinstance(result, JobResult):
            if isinstance(result.job.what, str):
                job_info = {
                    "type": "shell",
                    "command": result.job.what,
                }
            else:
                job_info = {
                    "type": "module",
                    "repr": repr(result.job.what),
                }
            return ret | {
                "type": "job",
                "action": "start" if isinstance(result, JobStartResult) else "end",
                "job": job_info,
            }
        elif isinstance(result, DeviceConfigResult):
            if isinstance(result, DeviceCreateResult):
                action_info = {
                    "action": "create",
                    "device": {
                        "cls_name": result.device._dev_cls.__name__,
                        "args": [repr(arg) for arg in result.device._dev_args],
                        "kwargs": [f"{k}={v!r}" for k, v in result.device._dev_kwargs.items()],
                    },
                }
            elif isinstance(result, DeviceMethodCallResult):
                action_info = {
                    "action": "method_call",
                    "method": {
                        "name": result.method_name,
                        "args": [repr(arg) for arg in result.args],
                        "kwargs": [f"{k}={v!r}" for k, v in result.kwargs.items()],
                    },
                }
            elif isinstance(result, DeviceAttrSetResult):
                action_info = {
                    "action": "attr_set",
                    "attr": {
                        "name": result.attr_name,
                        "value": result.value,
                        "old_value": result.old_value,
                    },
                }
            else:
                logging.warning(f"unhandled device config result: {result.__class__.__name__}")
                action_info = {"action": "unknown"}
            return ret | {
                "type": "device_config",
                "host": result.device.host.hostid,
                "netns": result.device.netns.name if result.device.netns and result.device.netns.name else "",
                "dev_id": result.device._id,
            } | action_info
        elif isinstance(result, MeasurementResult):
            if result.measurement_type == "ping":
                measurement_data = result.data
            elif result.measurement_type == "cpu":
                measurement_data = {
                    "utilization": result.data["cpu"].average,
                }
            elif result.measurement_type == "flow":
                agg_results = result.data["flow_results"]
                measurement_data = {
                    "generator_results": agg_results.generator_results.average,
                    "generator_cpu_stats": agg_results.generator_cpu_stats.average,
                    "receiver_results": agg_results.receiver_results.average,
                    "receiver_cpu_stats": agg_results.receiver_cpu_stats.average,
                }
            elif result.measurement_type == "tc":
                measurement_data = {
                    "rule_install_rate": result.data["rule_install_rate"].average,
                }
            elif result.measurement_type == "linuxperf":
                # linuxperf measurement just generates files
                measurement_data = {}
            else:
                logging.warning(f"unhandled measurement result type: {result.measurement_type}")
                measurement_data = None
            return ret | {
                "type": "measurement",
                "measurement_type": result.measurement_type,
                "data": measurement_data,
            }
        else:
            if result.data is not None:
                logging.warning(f"unhandled recipe result type: {repr(result)}, can't format its data")

            return ret | {
                "type": "unknown",
                "description": result.description,
            }
