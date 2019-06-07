import pprint
from contextlib import contextmanager

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam, ListParam
from lnst.Common.IpAddress import AF_INET, AF_INET6

from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import BaseSubConfigMixin

from lnst.RecipeCommon.Ping import PingTestAndEvaluate, PingConf
from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import IperfFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement
from lnst.RecipeCommon.Perf.Evaluators import NonzeroFlowEvaluator

class EnrtConfiguration(object):
    pass

class BaseEnrtRecipe(BaseSubConfigMixin, PingTestAndEvaluate, PerfRecipe):
    #common requirements parameters
    driver = StrParam(default="ixgbe")

    #common configuration parameters
    mtu = IntParam(mandatory=False)
    adaptive_rx_coalescing = BoolParam(mandatory=False)
    adaptive_tx_coalescing = BoolParam(mandatory=False)

    #common test parameters
    ip_versions = Param(default=("ipv4", "ipv6"))

    #common ping test params
    ping_parallel = BoolParam(default=False)
    ping_bidirect = BoolParam(default=False)
    ping_count = IntParam(default=100)
    ping_interval = StrParam(default=0.2)
    ping_psize = IntParam(default=None)

    #common perf test params
    perf_tests = Param(default=("tcp_stream", "udp_stream", "sctp_stream"))
    perf_tool_cpu = IntParam(mandatory=False)
    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_parallel_streams = IntParam(default=1)
    perf_msg_sizes = ListParam(default=[123])
    perf_reverse = BoolParam(default=False)

    net_perf_tool = Param(default=IperfFlowMeasurement)
    cpu_perf_tool = Param(default=StatCPUMeasurement)

    def test(self):
        with self._test_wide_context() as main_config:
            for sub_config in self.generate_sub_configurations(main_config):
                with self._sub_context(sub_config) as recipe_config:
                    self.do_tests(recipe_config)

    @contextmanager
    def _test_wide_context(self):
        config = self.test_wide_configuration()
        self.describe_test_wide_configuration(config)
        try:
            yield config
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self):
        return EnrtConfiguration()

    def test_wide_deconfiguration(self, config):
        #TODO check if anything is still applied and throw exception?
        return

    def describe_test_wide_configuration(self, config):
        description = self.generate_test_wide_description(config)
        self.add_result(True, "Summary of used Recipe parameters:\n{}".format(
                        pprint.pformat(self.params._to_dict())))
        self.add_result(True, "\n".join(description))

    def generate_test_wide_description(self, config):
        return [
            "Testwide configuration for recipe {} description:".format(
                self.__class__.__name__
            )
        ]

    @contextmanager
    def _sub_context(self, config):
        self.apply_sub_configuration(config)
        self.describe_sub_configuration(config)
        try:
            yield config
        finally:
            self.remove_sub_configuration(config)

    def describe_sub_configuration(self, config):
        description = self.generate_sub_configuration_description(config)
        self.add_result(True, "\n".join(description))

    def generate_sub_configuration_description(self, config):
        return ["Sub configuration description:"]

    def do_tests(self, recipe_config):
        self.do_ping_tests(recipe_config)
        self.do_perf_tests(recipe_config)

    def do_ping_tests(self, recipe_config):
        for ping_config in self.generate_ping_configurations(recipe_config):
            result = self.ping_test(ping_config)
            self.ping_evaluate_and_report(ping_config, result)

    def do_perf_tests(self, recipe_config):
        for perf_config in self.generate_perf_configurations(recipe_config):
            result = self.perf_test(perf_config)
            self.perf_report_and_evaluate(result)

    def generate_ping_configurations(self, config):
        for endpoint1, endpoint2 in self.generate_ping_endpoints(config):
            for ipv in self.params.ip_versions:
                ip_filter = {}
                if ipv == "ipv4":
                    ip_filter.update(family = AF_INET)
                elif ipv == "ipv6":
                    ip_filter.update(family = AF_INET6)
                    ip_filter.update(is_link_local = False)

                endpoint1_ips = endpoint1.ips_filter(**ip_filter)
                endpoint2_ips = endpoint2.ips_filter(**ip_filter)

                if len(endpoint1_ips) != len(endpoint2_ips):
                    raise LnstError("Source/destination ip lists are of different size.")

                ping_conf_list = []
                for src_addr, dst_addr in zip(endpoint1_ips, endpoint2_ips):
                    pconf = PingConf(client = endpoint1.netns,
                                     client_bind = src_addr,
                                     destination = endpoint2.netns,
                                     destination_address = dst_addr,
                                     count = self.params.ping_count,
                                     interval = self.params.ping_interval,
                                     size = self.params.ping_psize,
                                     )

                    ping_conf_list.append(pconf)

                    if self.params.ping_bidirect:
                        ping_conf_list.append(self._create_reverse_ping(pconf))

                    if not self.params.ping_parallel:
                        break

                yield ping_conf_list

    def generate_ping_endpoints(self, config):
        return []

    def generate_perf_configurations(self, config):
        for flows in self.generate_flow_combinations(config):
            perf_recipe_conf=dict(
                main_config=config,
                sub_config=config,
                flows=flows,
            )

            flows_measurement = self.params.net_perf_tool(
                flows,
                perf_recipe_conf
            )

            cpu_measurement_hosts = set()
            for flow in flows:
                cpu_measurement_hosts.add(flow.generator)
                cpu_measurement_hosts.add(flow.receiver)

            cpu_measurement = self.params.cpu_perf_tool(
                cpu_measurement_hosts,
                perf_recipe_conf,
            )

            perf_conf = PerfRecipeConf(
                measurements=[cpu_measurement, flows_measurement],
                iterations=self.params.perf_iterations,
            )

            perf_conf.register_evaluators(
                cpu_measurement, self.cpu_perf_evaluators
            )
            perf_conf.register_evaluators(
                flows_measurement, self.net_perf_evaluators
            )

            yield perf_conf

    def generate_flow_combinations(self, config):
        for client_nic, server_nic in self.generate_perf_endpoints(config):
            for ipv in self.params.ip_versions:
                if ipv == "ipv4":
                    family = AF_INET
                elif ipv == "ipv6":
                    family = AF_INET6

                client_bind = client_nic.ips_filter(family=family)[0]
                server_bind = server_nic.ips_filter(family=family)[0]

                for perf_test in self.params.perf_tests:
                    for size in self.params.perf_msg_sizes:
                        flow = PerfFlow(
                                type = perf_test,
                                generator = client_nic.netns,
                                generator_bind = client_bind,
                                receiver = server_nic.netns,
                                receiver_bind = server_bind,
                                msg_size = size,
                                duration = self.params.perf_duration,
                                parallel_streams = self.params.perf_parallel_streams,
                                cpupin = self.params.perf_tool_cpu if "perf_tool_cpu" in self.params else None
                                )
                        yield [flow]

                        if self.params.perf_reverse:
                            reverse_flow = self._create_reverse_flow(flow)
                            yield [reverse_flow]

    def generate_perf_endpoints(self, config):
        return []

    @property
    def cpu_perf_evaluators(self):
        return []

    @property
    def net_perf_evaluators(self):
        return [NonzeroFlowEvaluator()]

    def _create_reverse_flow(self, flow):
        rev_flow = PerfFlow(
                    type = flow.type,
                    generator = flow.receiver,
                    generator_bind = flow.receiver_bind,
                    receiver = flow.generator,
                    receiver_bind = flow.generator_bind,
                    msg_size = flow.msg_size,
                    duration = flow.duration,
                    parallel_streams = flow.parallel_streams,
                    cpupin = flow.cpupin
                    )
        return rev_flow

    def _create_reverse_ping(self, pconf):
        return PingConf(
            client = pconf.destination,
            client_bind = pconf.destination_address,
            destination = pconf.client,
            destination_address = pconf.client_bind,
            count = pconf.ping_count,
            interval = pconf.ping_interval,
            size = pconf.ping_psize,
        )
