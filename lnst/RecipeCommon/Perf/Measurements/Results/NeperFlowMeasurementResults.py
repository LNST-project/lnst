from lnst.RecipeCommon.Perf.Measurements.BaseFlowMeasurement import FlowMeasurementResults


class NeperFlowMeasurementResults(FlowMeasurementResults):
    @property
    def warmup_end(self):
        if self.flow.type != "tcp_crr":
            return super().warmup_end

        if self.warmup_duration == 0:
            return self.start_timestamp

        return max(
            [
                parallel.start_timestamp + self.warmup_duration
                for parallel in self.generator_results
            ]
        )

    @property
    def warmdown_start(self):
        if self.flow.type != "tcp_crr":
            return super().warmdown_start

        if self.warmup_duration == 0:
            return self.end_timestamp

        return min(
            [
                parallel.end_timestamp - self.warmup_duration
                for parallel in self.generator_results
            ]
        )
