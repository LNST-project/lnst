from lnst.Common.Parameters import Param

from lnst.RecipeCommon.Perf.Measurements.StatCPUMeasurement import StatCPUMeasurement

from lnst.Recipes.ENRT.MeasurementGenerators.BaseMeasurementGenerator import BaseMeasurementGenerator

class HypervisorsStatCPUMeasurementGenerator(BaseMeasurementGenerator):
    cpu_perf_tool = Param(default=StatCPUMeasurement)

    def generate_perf_measurements_combinations(self, config):
        combinations = super().generate_perf_measurements_combinations(config)
        for combination in combinations:
            yield [
                self.params.cpu_perf_tool(self.hypervisor_hosts)
            ] + combination

    @property
    def hypervisor_hosts(self):
        return set()
