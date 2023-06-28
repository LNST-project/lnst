import textwrap

from lnst.Controller.RecipeResults import ResultType
from lnst.RecipeCommon.Perf.Measurements.MeasurementError import MeasurementError
from lnst.RecipeCommon.Perf.Measurements.BaseMeasurement import BaseMeasurement
from lnst.RecipeCommon.Perf.Measurements.Results import FlowMeasurementResults, AggregatedFlowMeasurementResults
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
                 generator_port=None,
                 receiver_nic=None,
                 receiver_port=None,
                 msg_size=None,
                 generator_cpupin=None,
                 receiver_cpupin=None,
                 aggregated_flow=False,
                 warmup_duration=0):
        self._type = type

        self._generator = generator
        self._generator_bind = generator_bind
        self._generator_nic = generator_nic
        self._generator_port = generator_port
        self._receiver = receiver
        self._receiver_bind = receiver_bind
        self._receiver_nic = receiver_nic
        self._receiver_port = receiver_port

        self._msg_size = msg_size
        self._duration = duration
        self._parallel_streams = parallel_streams
        self._generator_cpupin = generator_cpupin
        self._receiver_cpupin = receiver_cpupin
        self._aggregated_flow=aggregated_flow
        self._warmup_duration = warmup_duration

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
    def generator_port(self):
        return self._generator_port

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
    def generator_cpupin(self):
        return self._generator_cpupin

    @property
    def receiver_cpupin(self):
        return self._receiver_cpupin

    @property
    def aggregated_flow(self):
        return self._aggregated_flow

    @property
    def warmup_duration(self):
        return self._warmup_duration

    def __repr__(self):
        string = """
        Flow(
            type={type},
            generator={generator}, 
            generator_bind={generator_bind},
            generator_nic={generator_nic},
            generator_port={generator_port},
            receiver={receiver}, 
            receiver_bind={receiver_bind},
            receiver_nic={receiver_nic},
            receiver_port={receiver_port},
            msg_size={msg_size}, 
            duration={duration},
            parallel_streams={parallel_streams},
            generator_cpupin={generator_cpupin},
            receiver_cpupin={receiver_cpupin},
            aggregated_flow={aggregated_flow}
            warmup_duration={warmup_duration},
        )""".format(
            type=self.type,
            generator=str(self.generator),
            generator_bind=self.generator_bind,
            generator_nic=self.generator_nic,
            generator_port=self.generator_port,
            receiver=str(self.receiver),
            receiver_bind=self.receiver_bind,
            receiver_nic=self.receiver_nic,
            receiver_port=self.receiver_port,
            msg_size=self.msg_size,
            duration=self.duration,
            parallel_streams=self.parallel_streams,
            generator_cpupin=self.generator_cpupin,
            receiver_cpupin=self.receiver_cpupin,
            aggregated_flow=self._aggregated_flow,
            warmup_duration=self._warmup_duration
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
        desc.append(flow_results.describe())

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
             generator_cpupin=None,
             receiver_cpupin=None,
             aggregated_flow=True,
             warmup_duration=sample_flow.warmup_duration
        )

        aggregated_result = AggregatedFlowMeasurementResults(
                sample_result.measurement, dummy_flow)

        nr_iterations = len(sample_result.individual_results)
        for i in range(nr_iterations):
            parallel_result = FlowMeasurementResults(
                    measurement=sample_result.measurement,
                    flow=dummy_flow,
                    warmup_duration=dummy_flow.warmup_duration
            )
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
