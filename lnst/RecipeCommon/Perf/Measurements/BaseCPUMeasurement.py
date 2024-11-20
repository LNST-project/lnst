from lnst.Controller.RecipeResults import MeasurementResult, ResultType
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results import AggregatedCPUMeasurementResults


class BaseCPUMeasurement(BaseMeasurement):
    def aggregate_results(self, old, new):
        aggregated = []
        if old is None:
            old = [None] * len(new)
        for old_measurements, new_measurements in zip(old, new):
            aggregated.append(self._aggregate_hostcpu_results(
                old_measurements, new_measurements))
        return aggregated

    @classmethod
    def report_results(cls, recipe, results):
        results_by_host = cls._divide_results_by_host(results)
        for host_results in list(results_by_host.values()):
            cls._report_host_results(recipe, host_results)

    @classmethod
    def _divide_results_by_host(cls, results):
        results_by_host = {}
        for result in results:
            if result.host not in results_by_host:
                results_by_host[result.host] = []
            results_by_host[result.host].append(result)
        return results_by_host

    @classmethod
    def _report_host_results(cls, recipe, results):
        if not len(results):
            return

        cpu_data = {result.cpu: result.utilization for result in results}

        desc = [result.describe() for result in results]

        recipe.add_custom_result(
            MeasurementResult(
                "cpu",
                result=(
                    ResultType.PASS
                    if all(res.measurement_success for res in results)
                    else ResultType.FAIL
                ),
                description="\n".join(desc),
                data=cpu_data,
            )
        )

    def _aggregate_hostcpu_results(self, old, new):
        if (old is not None and
                (old.host is not new.host or old.cpu != new.cpu)):
            raise MeasurementError("Aggregating incompatible CPU Results")

        new_result = AggregatedCPUMeasurementResults(self, new.host, new.cpu)
        new_result.add_results(old)
        new_result.add_results(new)
        return new_result
