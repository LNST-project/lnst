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
                parallel[self.warmup_duration - 1].end_timestamp
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
                parallel[-self.warmup_duration].start_timestamp
                for parallel in self.generator_results
            ]
        )
