from lnst.RecipeCommon.Perf.Results import ParallelPerfResult
from lnst.RecipeCommon.Perf.Measurements.Results.FlowMeasurementResults import (
    FlowMeasurementResults,
)
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError


class XDPBenchMeasurementResults(FlowMeasurementResults):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._generator_results = ParallelPerfResult()  # multiple instances of pktgen
        self._receiver_results = ParallelPerfResult()  # single instance of xdpbench

    @property
    def metrics(self) -> list[str]:
        return ['generator_results', 'receiver_results']

    def add_results(self, results):
        if results is None:
            return
        if isinstance(results, XDPBenchMeasurementResults):
            self.generator_results.append(results.generator_results)
            self.receiver_results.append(results.receiver_results)
        else:
            raise MeasurementError("Adding incorrect results.")

    def time_slice(self, start, end):
        result_copy = XDPBenchMeasurementResults(
            self.measurement, self.flow, warmup_duration=0
        )

        result_copy.generator_results = self.generator_results.time_slice(start, end)
        result_copy.receiver_results = self.receiver_results.time_slice(start, end)

        return result_copy

    def describe(self) -> str:
        generator = self.generator_results
        receiver = self.receiver_results

        desc = []
        desc.append(str(self.flow))
        desc.append(
            "Generator generated: {tput:,f} {unit} per second.".format(
                tput=generator.average, unit=generator.unit
            )
        )
        desc.append(
            "Receiver processed: {tput:,f} {unit} per second.".format(
                tput=receiver.average, unit=receiver.unit
            )
        )

        return "\n".join(desc)
