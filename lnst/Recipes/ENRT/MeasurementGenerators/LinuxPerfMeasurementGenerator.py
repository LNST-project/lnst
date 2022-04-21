from lnst.Recipes.ENRT.MeasurementGenerators.BaseMeasurementGenerator import (
    BaseMeasurementGenerator,
)
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import (
    BaseMeasurement,
)
from lnst.RecipeCommon.Perf.Measurements.LinuxPerfMeasurement import (
    LinuxPerfMeasurement,
)
from lnst.Common.Parameters import BoolParam, StrParam
from lnst.Controller.Host import Host

import os

class LinuxPerfMeasurementGenerator(BaseMeasurementGenerator):
    do_linuxperf_measurement = BoolParam(default=False)
    linuxperf_intr_fname = StrParam(default="intr.data")
    linuxperf_iperf_fname = StrParam(default="iperf.data")

    def generate_perf_measurements_combinations(self, config):
        combinations = super().generate_perf_measurements_combinations(config)

        if not self.params.do_linuxperf_measurement:
            return combinations

        # create linuxperf data folder
        linuxperf_data_folder: str = os.path.abspath(
            os.path.join(self.current_run.log_dir, "linuxperf-data")
        )
        os.mkdir(linuxperf_data_folder)

        for combination in combinations:
            measurement: BaseMeasurement = LinuxPerfMeasurement(
                self.matched,
                self.params.linuxperf_intr_fname,
                self.params.dev_intr_cpu,
                self.params.linuxperf_iperf_fname,
                self.params.perf_tool_cpu,
                data_folder=linuxperf_data_folder,
                recipe_conf=config,
            )

            yield [measurement] + combination
