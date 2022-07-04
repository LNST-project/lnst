from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurementResults
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult

class CPUMeasurementResults(BaseMeasurementResults):
    def __init__(self, measurement, host, cpu):
        super(CPUMeasurementResults, self).__init__(measurement)
        self._host = host
        self._cpu = cpu
        self._utilization = None

    @property
    def host(self):
        return self._host

    @property
    def cpu(self):
        return self._cpu

    @property
    def utilization(self):
        return self._utilization

    @utilization.setter
    def utilization(self, value):
        self._utilization = value

class AggregatedCPUMeasurementResults(CPUMeasurementResults):
    def __init__(self, measurement, host, cpu):
        super(AggregatedCPUMeasurementResults, self).__init__(measurement, host, cpu)
        self._individual_results = []

    @property
    def individual_results(self):
        return self._individual_results

    @property
    def utilization(self):
        return SequentialPerfResult([i.utilization
                                     for i in self.individual_results])

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedCPUMeasurementResults):
            self.individual_results.extend(results.individual_results)
        elif isinstance(results, CPUMeasurementResults):
            self.individual_results.append(results)
        else:
            raise MeasurementError("Adding incorrect results.")

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

        cpu_data = {}
        desc = ["CPU Utilization on host {host}:".format(
                    host=results[0].host.hostid)]
        for result in results:
            utilization = result.utilization
            cpu_data[result.cpu] = utilization
            desc.append("cpu '{cpu}': {average:.2f} +-{deviation:.2f} {unit} per second"
                    .format(cpu=result.cpu,
                            average=utilization.average,
                            deviation=utilization.std_deviation,
                            unit=utilization.unit))

        recipe.add_result(ResultType.PASS, "\n".join(desc), data=cpu_data)

    def _aggregate_hostcpu_results(self, old, new):
        if (old is not None and
                (old.host is not new.host or old.cpu != new.cpu)):
            raise MeasurementError("Aggregating incompatible CPU Results")

        new_result = AggregatedCPUMeasurementResults(self, new.host, new.cpu)
        new_result.add_results(old)
        new_result.add_results(new)
        return new_result
