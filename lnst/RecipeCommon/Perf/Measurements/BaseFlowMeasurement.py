import textwrap

from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurementResults
from lnst.RecipeCommon.Perf.Results import SequentialPerfResult
from lnst.RecipeCommon.Perf.Results import ParallelPerfResult

class Flow(object):
    def __init__(self,
                 type,
                 generator,
                 generator_bind,
                 receiver,
                 receiver_bind,
                 duration,
                 parallel_streams,
                 generator_nic=None,
                 receiver_nic=None,
                 receiver_port=None,
                 msg_size=None,
                 cpupin=None,
                 aggregated_flow=False):
        self._type = type

        self._generator = generator
        self._generator_bind = generator_bind
        self._generator_nic = generator_nic
        self._receiver = receiver
        self._receiver_bind = receiver_bind
        self._receiver_nic = receiver_nic
        self._receiver_port = receiver_port

        self._msg_size = msg_size
        self._duration = duration
        self._parallel_streams = parallel_streams
        self._cpupin = cpupin
        self._aggregated_flow=aggregated_flow

    @property
    def type(self):
        return self._type

    @property
    def generator(self):
        return self._generator

    @property
    def generator_bind(self):
        return self._generator_bind

    @property
    def generator_nic(self):
        return self._generator_nic

    @property
    def receiver(self):
        return self._receiver

    @property
    def receiver_bind(self):
        return self._receiver_bind

    @property
    def receiver_nic(self):
        return self._receiver_nic

    @property
    def receiver_port(self):
        return self._receiver_port

    @property
    def msg_size(self):
        return self._msg_size

    @property
    def duration(self):
        return self._duration

    @property
    def parallel_streams(self):
        return self._parallel_streams

    @property
    def cpupin(self):
        return self._cpupin

    @property
    def aggregated_flow(self):
        return self._aggregated_flow

    def __repr__(self):
        string = """
        Flow(
            type={type},
            generator={generator}, 
            generator_bind={generator_bind},
            generator_nic={generator_nic},
            receiver={receiver}, 
            receiver_bind={receiver_bind},
            receiver_nic={receiver_nic},
            receiver_port={receiver_port},
            msg_size={msg_size}, 
            duration={duration},
            parallel_streams={parallel_streams},
            cpupin={cpupin},
            aggregated_flow={aggregated_flow},
        )""".format(
            type=self.type,
            generator=str(self.generator),
            generator_bind=self.generator_bind,
            generator_nic=self.generator_nic,
            receiver=str(self.receiver),
            receiver_bind=self.receiver_bind,
            receiver_nic=self.receiver_nic,
            receiver_port=self.receiver_port,
            msg_size=self.msg_size,
            duration=self.duration,
            parallel_streams=self.parallel_streams,
            cpupin=self.cpupin,
            aggregated_flow=self._aggregated_flow,
        )
        string = textwrap.dedent(string).strip()
        return string

class NetworkFlowTest(object):
    def __init__(self, flow, server_job, client_job):
        self._flow = flow
        self._server_job = server_job
        self._client_job = client_job

    @property
    def flow(self):
        return self._flow

    @property
    def server_job(self):
        return self._server_job

    @property
    def client_job(self):
        return self._client_job

class FlowMeasurementResults(BaseMeasurementResults):
    def __init__(self, measurement, flow):
        super(FlowMeasurementResults, self).__init__(measurement)
        self._flow = flow
        self._generator_results = None
        self._generator_cpu_stats = None
        self._receiver_results = None
        self._receiver_cpu_stats = None

    @property
    def flow(self):
        return self._flow

    @property
    def generator_results(self):
        return self._generator_results

    @generator_results.setter
    def generator_results(self, value):
        self._generator_results = value

    @property
    def generator_cpu_stats(self):
        return self._generator_cpu_stats

    @generator_cpu_stats.setter
    def generator_cpu_stats(self, value):
        self._generator_cpu_stats = value

    @property
    def receiver_results(self):
        return self._receiver_results

    @receiver_results.setter
    def receiver_results(self, value):
        self._receiver_results = value

    @property
    def receiver_cpu_stats(self):
        return self._receiver_cpu_stats

    @receiver_cpu_stats.setter
    def receiver_cpu_stats(self, value):
        self._receiver_cpu_stats = value

    @property
    def start_timestamp(self):
        return min(
            [
                self.generator_results.start_timestamp,
                self.generator_cpu_stats.start_timestamp,
                self.receiver_results.start_timestamp,
                self.receiver_cpu_stats.start_timestamp,
            ]
        )

    @property
    def end_timestamp(self):
        return max(
            [
                self.generator_results.end_timestamp,
                self.generator_cpu_stats.end_timestamp,
                self.receiver_results.end_timestamp,
                self.receiver_cpu_stats.end_timestamp,
            ]
        )

    def time_slice(self, start, end):
        result_copy = FlowMeasurementResults(self.measurement, self.flow)

        result_copy.generator_cpu_stats = self.generator_cpu_stats.time_slice(start, end)
        result_copy.receiver_cpu_stats = self.receiver_cpu_stats.time_slice(start, end)

        result_copy.generator_results = self.generator_results.time_slice(start, end)
        result_copy.receiver_results = self.receiver_results.time_slice(start, end)

        return result_copy


class AggregatedFlowMeasurementResults(FlowMeasurementResults):
    def __init__(self, measurement, flow):
        super(FlowMeasurementResults, self).__init__(measurement)
        self._flow = flow
        self._generator_results = SequentialPerfResult()
        self._generator_cpu_stats = SequentialPerfResult()
        self._receiver_results = SequentialPerfResult()
        self._receiver_cpu_stats = SequentialPerfResult()
        self._individual_results = []

    @property
    def individual_results(self):
        return self._individual_results

    def add_results(self, results):
        if results is None:
            return
        elif isinstance(results, AggregatedFlowMeasurementResults):
            self.individual_results.extend(results.individual_results)
            self.generator_results.extend(results.generator_results)
            self.generator_cpu_stats.extend(results.generator_cpu_stats)
            self.receiver_results.extend(results.receiver_results)
            self.receiver_cpu_stats.extend(results.receiver_cpu_stats)
        elif isinstance(results, FlowMeasurementResults):
            self.individual_results.append(results)
            self.generator_results.append(results.generator_results)
            self.generator_cpu_stats.append(results.generator_cpu_stats)
            self.receiver_results.append(results.receiver_results)
            self.receiver_cpu_stats.append(results.receiver_cpu_stats)
        else:
            raise MeasurementError("Adding incorrect results.")

class BaseFlowMeasurement(BaseMeasurement):
    @property
    def flows(self):
        raise NotImplementedError()

    @classmethod
    def report_results(cls, recipe, results):
        for flow_results in results:
            cls._report_flow_results(recipe, flow_results)

        # report aggregated results
        if len(results) > 1:
            aggregated_flow_results = cls.aggregate_multi_flow_results(results)
            for flow_results in aggregated_flow_results:
                cls._report_flow_results(recipe, flow_results)

    @staticmethod
    def _invalid_flow_duration(result: FlowMeasurementResults) -> bool:
        if result.duration <= 0:
            return True
        return False

    @classmethod
    def _report_flow_results(cls, recipe, flow_results):
        generator = flow_results.generator_results
        generator_cpu = flow_results.generator_cpu_stats
        receiver = flow_results.receiver_results
        receiver_cpu = flow_results.receiver_cpu_stats

        desc = []
        desc.append(str(flow_results.flow))
        desc.append("Generator measured throughput: {tput:.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second."
                .format(tput=generator.average,
                        deviation=generator.std_deviation,
                        percentage=cls._deviation_percentage(generator),
                        unit=generator.unit))
        desc.append("Generator process CPU data: {cpu:.2f} +-{cpu_deviation:.2f} {cpu_unit} per second."
                .format(cpu=generator_cpu.average,
                        cpu_deviation=generator_cpu.std_deviation,
                        cpu_unit=generator_cpu.unit))
        desc.append("Receiver measured throughput: {tput:.2f} +-{deviation:.2f}({percentage:.2f}%) {unit} per second."
                .format(tput=receiver.average,
                        deviation=receiver.std_deviation,
                        percentage=cls._deviation_percentage(receiver),
                        unit=receiver.unit))
        desc.append("Receiver process CPU data: {cpu:.2f} +-{cpu_deviation:.2f} {cpu_unit} per second."
                .format(cpu=receiver_cpu.average,
                        cpu_deviation=receiver_cpu.std_deviation,
                        cpu_unit=receiver_cpu.unit))

        recipe_result = ResultType.PASS
        metrics = {"Generator": generator, "Generator process": generator_cpu,
                   "Receiver": receiver, "Receiver process": receiver_cpu}
        for name, result in metrics.items():
            if cls._invalid_flow_duration(result):
                recipe_result = ResultType.FAIL
                desc.append("{} has invalid duration!".format(name))

        # TODO add flow description
        recipe.add_result(recipe_result, "\n".join(desc), data = dict(
                    generator_flow_data=generator,
                    generator_cpu_data=generator_cpu,
                    receiver_flow_data=receiver,
                    receiver_cpu_data=receiver_cpu,
                    flow_results=flow_results))

    def aggregate_results(self, old, new):
        aggregated = []
        if old is None:
            old = [None] * len(new)
        for old_flow, new_flow in zip(old, new):
            aggregated.append(self._aggregate_flows(old_flow, new_flow))
        return aggregated

    def _aggregate_flows(self, old_flow, new_flow):
        if old_flow is not None and old_flow.flow is not new_flow.flow:
            raise MeasurementError("Aggregating incompatible Flows")

        new_result = AggregatedFlowMeasurementResults(measurement=self, flow=new_flow.flow)

        new_result.add_results(old_flow)
        new_result.add_results(new_flow)
        return new_result

    @classmethod
    def _deviation_percentage(cls, result):
        try:
            return (result.std_deviation/result.average) * 100
        except ZeroDivisionError:
            return float('inf') if result.std_deviation >= 0 else float("-inf")

    @staticmethod
    def aggregate_multi_flow_results(results):
        if len(results) == 1:
            return results

        sample_result = results[0]
        sample_flow = sample_result.flow
        dummy_flow = Flow(
             type=sample_flow.type,
             generator=sample_flow.generator,
             generator_bind=sample_flow.generator_bind,
             generator_nic=sample_flow.generator_nic,
             receiver=sample_flow.receiver,
             receiver_bind=sample_flow.receiver_bind,
             receiver_nic=sample_flow.receiver_nic,
             receiver_port=None,
             msg_size=sample_flow.msg_size,
             duration=sample_flow.duration,
             parallel_streams=sample_flow.parallel_streams,
             cpupin=None,
             aggregated_flow=True,
        )

        aggregated_result = AggregatedFlowMeasurementResults(
                sample_result.measurement, dummy_flow)

        nr_iterations = len(sample_result.individual_results)
        for i in range(nr_iterations):
            parallel_result = FlowMeasurementResults(
                    measurement=sample_result.measurement,
                    flow=dummy_flow)
            parallel_result.generator_results = ParallelPerfResult()
            parallel_result.generator_cpu_stats = ParallelPerfResult()
            parallel_result.receiver_results = ParallelPerfResult()
            parallel_result.receiver_cpu_stats = ParallelPerfResult()

            for result in results:
                flow_result = result.individual_results[i]
                parallel_result.generator_results.append(flow_result.generator_results)
                parallel_result.receiver_results.append(flow_result.receiver_results)
                parallel_result.generator_cpu_stats.append(flow_result.generator_cpu_stats)
                parallel_result.receiver_cpu_stats.append(flow_result.receiver_cpu_stats)

            aggregated_result.add_results(parallel_result)

        return [aggregated_result]
