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

        for combination in combinations:
            res: list[BaseMeasurement]
            if self.params.do_linuxperf_measurement:
                measurement: BaseMeasurement = LinuxPerfMeasurement(
                    self.matched,
                    self.linuxperf_cpus,
                    data_folder=linuxperf_data_folder,
                    recipe_conf=config,
                )
                res = [measurement] + combination
            else:
                res = combination

            yield res
