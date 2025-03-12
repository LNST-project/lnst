import os

from lnst.Recipes.ENRT.MeasurementGenerators.BaseMeasurementGenerator import (
    BaseMeasurementGenerator,
)
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements import LinuxPerfMeasurement
from lnst.Common.Parameters import BoolParam
from lnst.Controller.Host import Host


class LinuxPerfMeasurementGenerator(BaseMeasurementGenerator):
    do_linuxperf_measurement = BoolParam(default=False)

    @property
    def linuxperf_hosts(self) -> list[Host]:
        return self.matched

    def generate_perf_measurements_combinations(self, config):
        combinations = super().generate_perf_measurements_combinations(config)

        if not self.params.do_linuxperf_measurement:
            yield from combinations
            return

        # create linuxperf data folder
        linuxperf_data_folder: str = os.path.abspath(
            os.path.join(self.current_run.log_dir, "linuxperf-data")
        )
        try:
            os.mkdir(linuxperf_data_folder)
        except FileExistsError:
            pass

        for combination in combinations:
            measurement: BaseMeasurement = LinuxPerfMeasurement(
                hosts=self.linuxperf_hosts,
                data_folder=linuxperf_data_folder,
                recipe_conf=config,
            )
            yield [measurement] + combination
