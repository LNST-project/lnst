from lnst.Common.Parameters import Param

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements.StatCPUMeasurement import StatCPUMeasurement

from lnst.Recipes.ENRT.MeasurementGenerators.BaseMeasurementGenerator import BaseMeasurementGenerator

class FlowEndpointsStatCPUMeasurementGenerator(BaseMeasurementGenerator):
    cpu_perf_tool = Param(default=StatCPUMeasurement)

    def generate_perf_measurements_combinations(self, config):
        combinations = super().generate_perf_measurements_combinations(config)
        for combination in combinations:
            cpu_measurement_hosts = self.extract_endpoints(config, combination)
            yield [
                self.params.cpu_perf_tool(cpu_measurement_hosts)
            ] + combination

    def extract_endpoints(self, config, measurements):
        endpoints = set()
        for measurement in measurements:
            if isinstance(measurement, BaseFlowMeasurement):
                for flow in measurement.flows:
                    endpoints.add(flow.generator)
                    endpoints.add(flow.receiver)
        return endpoints
