import os

from lnst.Recipes.ENRT.MeasurementGenerators.BaseMeasurementGenerator import (
    BaseMeasurementGenerator,
)
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurement,
)
from lnst.RecipeCommon.Perf.Measurements.LinuxPerfMeasurement import (
    LinuxPerfMeasurement,
)
from lnst.Common.Parameters import (
    BoolParam,
    IntParam,
    ListParam,
)
from lnst.Common.LnstError import LnstError
from lnst.Controller.Host import Host


class LinuxPerfMeasurementGenerator(BaseMeasurementGenerator):
    do_linuxperf_measurement = BoolParam(default=False)
    linuxperf_cpus_override = ListParam(type=ListParam(type=IntParam()), mandatory=False)

    def generate_perf_measurements_combinations(self, config):
        combinations = super().generate_perf_measurements_combinations(config)

        if self.params.do_linuxperf_measurement:
            # create linuxperf data folder
            linuxperf_data_folder: str = os.path.abspath(
                os.path.join(self.current_run.log_dir, "linuxperf-data")
            )
            try:
                os.mkdir(linuxperf_data_folder)
            except FileExistsError:
                pass

        profiled_cpu_groups: dict[Host, list[list[int]]] = {}
        if self.params.get("linuxperf_cpus_override"):
            profiled_cpu_groups = self._parse_override_param(self.params.linuxperf_cpus_override)
        else:
            profiled_cpu_groups = getattr(self, "linuxperf_cpus", {})

        # TODO: in case no group of cpus is in the list, we may simply run
        # profiler without the cpu specified, however this requires additional
        # changes in the LinuxPerfMeasurement class; for now, let's just
        # disallow this by raising an exception
        if self.params.do_linuxperf_measurement and not profiled_cpu_groups:
            raise LnstError(
                "Cannot profile empty list of cpus when do_linuxperf_measurement parameter is specified"
            )

        for combination in combinations:
            res: list[BaseMeasurement]
            if self.params.do_linuxperf_measurement:
                measurement: BaseMeasurement = LinuxPerfMeasurement(
                    profiled_cpu_groups,
                    data_folder=linuxperf_data_folder,
                    recipe_conf=config,
                )
                res = [measurement] + combination
            else:
                res = combination

            yield res

    def _parse_override_param(self, param):
        result = {}

        for host in param:
            try:
                matched_host = getattr(self.matched, host)
            except AttributeError:
                raise Exception(
                    f"Host {host} not found in matched hosts, while parsing {param}"
                )

            result[matched_host] = param[host]

        return result
