from .BaseMeasurementGenerator import BaseMeasurementGenerator
from lnst.RecipeCommon.Perf.Measurements.LatencyMeasurement import LatencyMeasurement

from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import BaseFlowMeasurement
from lnst.Common.Parameters import IntParam
from lnst.Common.IpAddress import Ip4Address, Ip6Address


class LatencyMeasurementGenerator(BaseMeasurementGenerator):
    latency_packets_count = IntParam(default=10)
    latency_packet_size = IntParam(default=64)
    latency_measurement_port = IntParam(default=19999)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.params.latency_packets_count < 3:
            raise ValueError("At least 3 samples are required for latency measurement")

    @property
    def cache_poison_tool(self, recipe_conf) -> callable:
        """
        Cache poison tool is used between latency measurements to poison
        cache so the last latency measurement packet will trigger cache
        miss machinery.

        Function should be returned.
        If no cache poisoning is needed, return None.
        """
        raise NotImplementedError(
            "cache_poison_tool needs to be implemented by parent class"
        )

    def generate_perf_measurements_combinations(self, config):
        combinations = super().generate_perf_measurements_combinations(config)

        combs = list(combinations)

        for combination in combs:
            com = list(combination)

            for measurement in combination:
                if not isinstance(measurement, BaseFlowMeasurement):
                    continue

                latency_measurement = LatencyMeasurement(
                    flows=measurement.flows,
                    recipe_conf=config,
                    port=self.params.latency_measurement_port,
                    payload_size=self.params.latency_packet_size,
                    samples_count=self.params.latency_packets_count,
                    cache_poison_tool=self.cache_poison_tool,
                )

                yield [latency_measurement] + com
