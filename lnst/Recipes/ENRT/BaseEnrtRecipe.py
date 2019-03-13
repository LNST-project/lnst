import re
from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.ExecCmd import exec_cmd
from lnst.Controller.Recipe import BaseRecipe, RecipeError

from lnst.RecipeCommon.Ping import PingTestAndEvaluate, PingConf
from lnst.RecipeCommon.Perf.Recipe import Recipe as PerfRecipe
from lnst.RecipeCommon.Perf.Recipe import RecipeConf as PerfRecipeConf
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Perf.Measurements import IperfFlowMeasurement
from lnst.RecipeCommon.Perf.Measurements import StatCPUMeasurement

class EnrtConfiguration(object):
    def __init__(self):
        self._endpoint1 = None
        self._endpoint2 = None
        self._endpoint1_coalescing = None

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
    def endpoint1_coalescing(self):
        self._endpoint1_coalescing

    @endpoint1_coalescing.setter
    def endpoint1_coalescing(self, value):
        self._endpoint1_coalescing = value

class EnrtSubConfiguration(object):
    def __init__(self):
        self._ip_version = None
        self._perf_test = None
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
    perf_tests = Param(default=("tcp_stream", "udp_stream", "sctp_stream"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on")))

    driver = StrParam(default="ixgbe")

    adaptive_coalescing = BoolParam(default=True)

    mtu = IntParam(mandatory=False)

    dev_intr_cpu = IntParam(mandatory=False)
    perf_tool_cpu = IntParam(mandatory=False)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_parallel_streams = IntParam(default=1)
    perf_msg_size = IntParam(default=123)
    perf_reverse = BoolParam(mandatory=False)

    perf_usr_comment = StrParam(default="")

    perf_max_deviation = IntParam(default=10) #TODO required?

    net_perf_tool = Param(default=IperfFlowMeasurement)

    cpu_perf_tool = Param(default=StatCPUMeasurement)

    def test(self):
        main_config = self.test_wide_configuration()

        for sub_config in self.generate_sub_configurations(main_config):
            self.apply_sub_configuration(main_config, sub_config)

            for ping_config in self.generate_ping_configurations(main_config,
                                                                 sub_config):
                result = self.ping_test(ping_config)
                self.ping_evaluate_and_report(ping_config, result)

            for perf_config in self.generate_perf_configurations(main_config,
                                                                 sub_config):
                result = self.perf_test(perf_config)
                self.perf_report_and_evaluate(result)

            self.remove_sub_configuration(main_config, sub_config)

        self.test_wide_deconfiguration(main_config)

    def test_wide_configuration(self):
        raise NotImplementedError("Method must be defined by a child class.")

    def test_wide_deconfiguration(self, main_config):
        raise NotImplementedError("Method must be defined by a child class.")

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

        ethtool_offload_string = ""
        for name, value in sub_config.offload_settings.items():
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

        ethtool_offload_string = ""
        for name, value in sub_config.offload_settings.items():
            ethtool_offload_string += " %s %s" % (name, "on")

        #set all the offloads back to 'on' state
        client_netns.run("ethtool -K {} {}".format(client_nic.name,
                                                   ethtool_offload_string))
        server_netns.run("ethtool -K {} {}".format(server_nic.name,
                                                   ethtool_offload_string))

    def generate_ping_configurations(self, main_config, sub_config):
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

            yield PingConf(client = client_netns,
                           client_bind = client_bind,
                           destination = server_netns,
                           destination_address = server_bind)

    def generate_perf_configurations(self, main_config, sub_config):
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
                flow = PerfFlow(
                        type = perf_test,
                        generator = client_netns,
                        generator_bind = client_bind,
                        receiver = server_netns,
                        receiver_bind = server_bind,
                        msg_size = self.params.perf_msg_size,
                        duration = self.params.perf_duration,
                        parallel_streams = self.params.perf_parallel_streams,
                        cpupin = self.params.perf_tool_cpu if "perf_tool_cpu" in self.params else None
                        )

                flow_measurement = self.params.net_perf_tool([flow])
                yield PerfRecipeConf(
                        measurements=[
                            self.params.cpu_perf_tool([client_netns, server_netns]),
                            flow_measurement
                            ],
                        iterations=self.params.perf_iterations)

                if "perf_reverse" in self.params and self.params.perf_reverse:
                    reverse_flow = self._create_reverse_flow(flow)
                    reverse_flow_measurement = self.params.net_perf_tool([reverse_flow])
                    yield PerfRecipeConf(
                            measurements=[
                                self.params.cpu_perf_tool([server_netns, client_netns]),
                                reverse_flow_measurement
                                ],
                            iterations=self.params.perf_iterations)

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

    def _pin_dev_interrupts(self, dev, cpu):
        netns = dev.netns
        cpu_info = netns.run("lscpu").stdout
        regex = "CPU\(s\): *([0-9]*)"
        num_cpus = int(re.search(regex, cpu_info).groups()[0])
        if cpu < 0 or cpu > num_cpus - 1:
            raise RecipeError("Invalid CPU value given: %d. Accepted value %s." %
                              (cpu, "is: 0" if num_cpus == 1 else "are: 0..%d" %
                               (num_cpus - 1)))

        res = netns.run("grep {} /proc/interrupts | cut -f1 -d: | sed 's/ //'"
                        .format(dev.name))
        intrs = res.stdout
        split = res.stdout.split("\n")
        if len(split) == 1 and split[0] == '':
            res = netns.run("dev_irqs=/sys/class/net/{}/device/msi_irqs; "
                            "[ -d $dev_irqs ] && ls -1 $dev_irqs"
                            .format(dev.name))
            intrs = res.stdout

        for intr in intrs.split("\n"):
            try:
                int(intr)
                netns.run("echo -n {} > /proc/irq/{}/smp_affinity_list"
                          .format(cpu, intr.strip()))
            except:
                pass
