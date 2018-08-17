from lnst.Controller.Recipe import BaseRecipe
from lnst.RecipeCommon.PerfResult import MultiRunPerf

class PerfConf(object):
    def __init__(self,
                 perf_tool,
                 test_type,
                 generator, generator_bind,
                 receiver, receiver_bind,
                 msg_size, duration, iterations, streams):
        self._perf_tool = perf_tool
        self._test_type = test_type

        self._generator = generator
        self._generator_bind = generator_bind
        self._receiver = receiver
        self._receiver_bind = receiver_bind

        self._msg_size = msg_size
        self._duration = duration
        self._iterations = iterations
        self._streams = streams

    @property
    def perf_tool(self):
        return self._perf_tool

    @property
    def generator(self):
        return self._generator

    @property
    def generator_bind(self):
        return self._generator_bind

    @property
    def receiver(self):
        return self._receiver

    @property
    def receiver_bind(self):
        return self._receiver_bind

    @property
    def test_type(self):
        return self._test_type

    @property
    def msg_size(self):
        return self._msg_size

    @property
    def duration(self):
        return self._duration

    @property
    def iterations(self):
        return self._iterations

    @property
    def streams(self):
        return self._streams

class PerfMeasurementTool(object):
    @staticmethod
    def perf_measure(perf_conf):
        raise NotImplementedError

class PerfTestAndEvaluate(BaseRecipe):
    def perf_test(self, perf_conf):
        generator_measurements = MultiRunPerf()
        receiver_measurements = MultiRunPerf()
        for i in range(perf_conf.iterations):
            tx, rx = perf_conf.perf_tool.perf_measure(perf_conf)

            if tx:
                generator_measurements.append(tx)
            if rx:
                receiver_measurements.append(rx)

        return generator_measurements, receiver_measurements

    def perf_evaluate_and_report(self, perf_conf, results, baseline):
        self.perf_evaluate(perf_conf, results, baseline)

        self.perf_report(perf_conf, results, baseline)

    def perf_evaluate(self, perf_conf, results, baseline):
        generator, receiver = results

        if generator.average > 0:
            self.add_result(True, "Generator reported non-zero throughput")
        else:
            self.add_result(False, "Generator reported zero throughput")

        if receiver.average > 0:
            self.add_result(True, "Receiver reported non-zero throughput")
        else:
            self.add_result(False, "Receiver reported zero throughput")


    def perf_report(self, perf_conf, results, baseline):
        generator, receiver = results

        self.add_result(
                True,
                "Generator measured throughput: {tput} +-{deviation}({percentage:.2}%) {unit} per second"
                .format(tput=generator.average,
                        deviation=generator.std_deviation,
                        percentage=(generator.std_deviation/generator.average) * 100,
                        unit=generator.unit),
                data = generator)
        self.add_result(
                True,
                "Receiver measured throughput: {tput} +-{deviation}({percentage:.2}%) {unit} per second"
                .format(tput=receiver.average,
                        deviation=receiver.std_deviation,
                        percentage=(receiver.std_deviation/receiver.average) * 100,
                        unit=receiver.unit),
                data = receiver)
