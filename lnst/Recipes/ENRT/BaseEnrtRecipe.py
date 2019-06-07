import re
from contextlib import contextmanager

from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam, ListParam
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.ExecCmd import exec_cmd
from lnst.Controller.Recipe import BaseRecipe, RecipeError
from lnst.Controller.RecipeResults import ResultLevel

from lnst.RecipeCommon.Ping import PingTestAndEvaluate, PingConf
from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import IperfFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement
from lnst.RecipeCommon.Perf.Evaluators import NonzeroFlowEvaluator

class EnrtConfiguration(object):
    def __init__(self):
        self._endpoint1 = None
        self._endpoint2 = None
        self._params = None

    @property
    def endpoint1(self):
        return self._endpoint1

    @endpoint1.setter
    def endpoint1(self, value):
        self._endpoint1 = value

    @property
    def endpoint2(self):
        return self._endpoint2

    @endpoint2.setter
    def endpoint2(self, value):
        self._endpoint2 = value

    @property
    def params(self):
        return self._params

    @params.setter
    def params(self, value):
        self._params = value


class EnrtSubConfiguration(object):
    def __init__(self):
        self._ip_version = None
        self._offload_settings = None

    @property
    def ip_version(self):
        return self._ip_version

    @ip_version.setter
    def ip_version(self, value):
        self._ip_version = value

    @property
    def offload_settings(self):
        return self._offload_settings

    @offload_settings.setter
    def offload_settings(self, value):
        self._offload_settings = value

class BaseEnrtRecipe(PingTestAndEvaluate, PerfRecipe):
    ip_versions = Param(default=("ipv4", "ipv6"))

    ping_parallel = BoolParam(default=False)
    ping_bidirect  = BoolParam(default=False)
    ping_count = IntParam(default = 100)
    ping_interval = StrParam(default = 0.2)
    ping_psize = IntParam(default = None)

    perf_tests = Param(default=("tcp_stream", "udp_stream", "sctp_stream"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),))

    driver = StrParam(default="ixgbe")

    adaptive_rx_coalescing = BoolParam(mandatory=False)
    adaptive_tx_coalescing = BoolParam(mandatory=False)

    mtu = IntParam(mandatory=False)

    dev_intr_cpu = IntParam(mandatory=False)
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
                with self._sub_context(main_config, sub_config) as recipe_config:
                    for ping_config in self.generate_ping_configurations(main_config,
                                                                         sub_config):
                        result = self.ping_test(ping_config)
                        self.ping_evaluate_and_report(ping_config, result)

                    for perf_config in self.generate_perf_configurations(main_config,
                                                                         sub_config):
                        result = self.perf_test(perf_config)
                        self.perf_report_and_evaluate(result)

    @contextmanager
    def _test_wide_context(self):
        config = self.test_wide_configuration()
        try:
            yield config
        finally:
            self.test_wide_deconfiguration(config)

    def test_wide_configuration(self):
        raise NotImplementedError("Method must be defined by a child class.")

    def test_wide_deconfiguration(self, main_config):
        raise NotImplementedError("Method must be defined by a child class.")

    @contextmanager
    def _sub_context(self, main_config, sub_config):
        self.apply_sub_configuration(main_config, sub_config)
        try:
            yield (main_config, sub_config)
        finally:
            self.remove_sub_configuration(main_config, sub_config)

    def generate_sub_configurations(self, main_config):
        for offload_settings in self.params.offload_combinations:
            sub_config = EnrtSubConfiguration()
            sub_config.offload_settings = offload_settings

            yield sub_config

    def apply_sub_configuration(self, main_config, sub_config):
        client_nic = main_config.endpoint1
        server_nic = main_config.endpoint2
        client_netns = client_nic.netns
        server_netns = server_nic.netns

        if 'sctp_stream' in self.params.perf_tests:
            client_netns.run("iptables -I OUTPUT ! -o %s -p sctp -j DROP" %
                             client_nic.name)
            server_netns.run("iptables -I OUTPUT ! -o %s -p sctp -j DROP" %
                             server_nic.name)

        ethtool_offload_string = ""
        for name, value in list(sub_config.offload_settings.items()):
            ethtool_offload_string += " %s %s" % (name, value)

        client_netns.run("ethtool -K {} {}".format(client_nic.name,
                                                   ethtool_offload_string))
        server_netns.run("ethtool -K {} {}".format(server_nic.name,
                                                   ethtool_offload_string))

    def remove_sub_configuration(self, main_config, sub_config):
        client_nic = main_config.endpoint1
        server_nic = main_config.endpoint2
        client_netns = client_nic.netns
        server_netns = server_nic.netns

        if 'sctp_stream' in self.params.perf_tests:
            client_netns.run("iptables -D OUTPUT ! -o %s -p sctp -j DROP" %
                             client_nic.name)
            server_netns.run("iptables -D OUTPUT ! -o %s -p sctp -j DROP" %
                             server_nic.name)

        ethtool_offload_string = ""
        for name, value in list(sub_config.offload_settings.items()):
            ethtool_offload_string += " %s %s" % (name, "on")

        #set all the offloads back to 'on' state
        client_netns.run("ethtool -K {} {}".format(client_nic.name,
                                                   ethtool_offload_string))
        server_netns.run("ethtool -K {} {}".format(server_nic.name,
                                                   ethtool_offload_string))

    def generate_ping_configurations(self, main_config, sub_config):
        client_nic = main_config.endpoint1
        server_nic = main_config.endpoint2

        count = self.params.ping_count
        interval = self.params.ping_interval
        size = self.params.ping_psize
        common_args = {'count' : count, 'interval' : interval, 'size' : size}

        for ipv in self.params.ip_versions:
            kwargs = {}
            if ipv == "ipv4":
                kwargs.update(family = AF_INET)
            elif ipv == "ipv6":
                kwargs.update(family = AF_INET6)
                kwargs.update(is_link_local = False)

            client_ips = client_nic.ips_filter(**kwargs)
            server_ips = server_nic.ips_filter(**kwargs)
            if ipv == "ipv6":
                client_ips = client_ips[::-1]
                server_ips = server_ips[::-1]

            if len(client_ips) != len(server_ips) or len(client_ips) * len(server_ips) == 0:
                raise LnstError("Source/destination ip lists are of different size or empty.")

            ping_conf_list = []
            for src_addr, dst_addr in zip(client_ips, server_ips):
                pconf = PingConf(client = client_nic.netns,
                                 client_bind = src_addr,
                                 destination = server_nic.netns,
                                 destination_address = dst_addr,
                                 **common_args)

                ping_conf_list.append(pconf)

                if self.params.ping_bidirect:
                    rev_pconf = self._create_reverse_ping(pconf, common_args)
                    ping_conf_list.append(rev_pconf)

                if not self.params.ping_parallel:
                    break

            yield ping_conf_list

    def generate_perf_configurations(self, main_config, sub_config):
        client_nic = main_config.endpoint1
        server_nic = main_config.endpoint2
        client_netns = client_nic.netns
        server_netns = server_nic.netns

        flow_combinations = self.generate_flow_combinations(
            main_config, sub_config
        )

        for flows in flow_combinations:
            perf_recipe_conf=dict(
                main_config=main_config,
                sub_config=sub_config,
                flows=flows,
            )

            flows_measurement = self.params.net_perf_tool(
                flows,
                perf_recipe_conf
            )

            cpu_measurement = self.params.cpu_perf_tool(
                [client_netns, server_netns],
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

    def generate_flow_combinations(self, main_config, sub_config):
        client_nic = main_config.endpoint1
        server_nic = main_config.endpoint2
        client_netns = client_nic.netns
        server_netns = server_nic.netns
        for ipv in self.params.ip_versions:
            if ipv == "ipv4":
                family = AF_INET
            elif ipv == "ipv6":
                family = AF_INET6

            client_bind = client_nic.ips_filter(family=family)[0]
            server_bind = server_nic.ips_filter(family=family)[0]

            for perf_test in self.params.perf_tests:
                offload_values = list(sub_config.offload_settings.values())
                offload_items = list(sub_config.offload_settings.items())
                if ((perf_test == 'udp_stream' and ('gro', 'off') in offload_items)
                    or
                    (perf_test == 'sctp_stream' and 'off' in offload_values and
                    ('gso', 'on') in offload_items)):
                    continue

                for size in self.params.perf_msg_sizes:
                    flow = PerfFlow(
                            type = perf_test,
                            generator = client_netns,
                            generator_bind = client_bind,
                            receiver = server_netns,
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

    def _create_reverse_ping(self, pconf, args):
        rev_pconf = PingConf(
                    client = pconf.destination,
                    client_bind = pconf.destination_address,
                    destination = pconf.client,
                    destination_address = pconf.client_bind,
                    **args
                    )
        return rev_pconf

    def _pin_dev_interrupts(self, dev, cpu):
        netns = dev.netns
        cpu_info = netns.run("lscpu", job_level=ResultLevel.DEBUG).stdout
        regex = "CPU\(s\): *([0-9]*)"
        num_cpus = int(re.search(regex, cpu_info).groups()[0])
        if cpu < 0 or cpu > num_cpus - 1:
            raise RecipeError("Invalid CPU value given: %d. Accepted value %s." %
                              (cpu, "is: 0" if num_cpus == 1 else "are: 0..%d" %
                               (num_cpus - 1)))

        res = netns.run(
            "grep {} /proc/interrupts | cut -f1 -d: | sed 's/ //'".format(
                dev.name
            ),
            job_level=ResultLevel.DEBUG,

        )
        intrs = res.stdout
        split = res.stdout.split("\n")
        if len(split) == 1 and split[0] == "":
            res = netns.run(
                "dev_irqs=/sys/class/net/{}/device/msi_irqs; "
                "[ -d $dev_irqs ] && ls -1 $dev_irqs".format(dev.name),
                job_level=ResultLevel.DEBUG,
            )
            intrs = res.stdout

        for intr in intrs.split("\n"):
            try:
                int(intr)
                netns.run("echo -n {} > /proc/irq/{}/smp_affinity_list"
                          .format(cpu, intr.strip()))
            except:
                pass
