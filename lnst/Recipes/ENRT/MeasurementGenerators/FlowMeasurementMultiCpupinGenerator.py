from lnst.Common.Parameters import ListParam, StrParam
from lnst.Recipes.ENRT.MeasurementGenerators.BaseFlowMeasurementGenerator import BaseFlowMeasurementGenerator


class FlowMeasurementMultiCpupinGenerator(BaseFlowMeasurementGenerator):
    """
    :param perf_tool_generator_cpu:
        Parameter used by the :any:`generate_flow_combinations` generator. To
        indicate that the generator of the flow measurement should be pinned
        to a specific CPU core(s)
    :type perf_tool_generator_cpu: :any:`ListParam` (optional parameter)

    :param perf_tool_generator_cpu_policy:
        Allows user to control how the cpus specified through the
        `perf_tool_generator_cpu` parameter are assigned to instances of the
        performance measurement tool.

        This parameter is usually used when `perf_parallel_processes` is set to a value greater than one.
        The value can be:
         * `round-robin` - each of the processes will be pinned to exactly ONE cpu from the list defined by perf_tool_generator_cpu in round-robin fashion
         * `all` - each of the processes will be pinned to all cpus in the list defined by perf_tool_generator_cpu
    :type perf_tool_generator_cpu_policy: :any:`StrParam` (default `all`)

    :param perf_tool_receiver_cpu:
        Parameter used by the :any:`generate_flow_combinations` generator. To
        indicate that the receiver of the flow measurement should be pinned
        to a specific CPU core(s)
    :type perf_tool_receiver_cpu: :any:`ListParam` (optional parameter)

    :param perf_tool_receiver_cpu_policy:
        Allows user to control how the cpus specified through the
        `perf_tool_receiver_cpu` parameter are assigned to instances of the
        performance measurement tool.

        This parameter is usually used when `perf_parallel_processes` is set to a value greater than one.
        The value can be:
         * `round-robin` - each of the processes will be pinned to exactly ONE cpu from the list defined by perf_tool_receiver_cpu in round-robin fashion
         * `all` - each of the processes will be pinned to all cpus in the list defined by perf_tool_receiver_cpu
    :type perf_tool_receiver_cpu_policy: :any:`StrParam` (default `all`)
    """
    perf_tool_generator_cpu = ListParam(mandatory=False)
    perf_tool_receiver_cpu = ListParam(mandatory=False)
    perf_tool_generator_cpu_policy = StrParam(mandatory=False)
    perf_tool_receiver_cpu_policy = StrParam(mandatory=False)

    def generator_cpupin(self, process_no):
        return self._cpupin_based_on_policy(
            process_no,
            self.params.get('perf_tool_generator_cpu', None),
            self.params.get('perf_tool_generator_cpu_policy', None),
        )

    def receiver_cpupin(self, process_no):
        return self._cpupin_based_on_policy(
            process_no,
            self.params.get('perf_tool_receiver_cpu', None),
            self.params.get('perf_tool_receiver_cpu_policy', None),
        )
