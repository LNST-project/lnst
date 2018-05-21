
from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import AF_INET, AF_INET6

from lnst.Controller.Recipe import BaseRecipe

from lnst.RecipeCommon.Ping import PingTestAndEvaluate, PingConf
from lnst.RecipeCommon.Perf import PerfTestAndEvaluate, PerfConf
from lnst.RecipeCommon.IperfMeasurementTool import IperfMeasurementTool

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

class BaseEnrtRecipe(PingTestAndEvaluate, PerfTestAndEvaluate):
    ip_versions = Param(default=("ipv4", "ipv6"))
    perf_tests = Param(default=("tcp_stream", "udp_stream", "sctp_stream"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on")))

    adaptive_coalescing = BoolParam(default=True)

    mtu = IntParam(mandatory=False)

    dev_intr_cpu = IntParam(default=0)

    perf_duration = IntParam(default=60)
    perf_iterations = IntParam(default=5)
    perf_streams = IntParam(default=1)
    perf_msg_size = IntParam(default=123)

    perf_usr_comment = StrParam(default="")

    perf_max_deviation = IntParam(default=10) #TODO required?

    perf_tool = Param(default=IperfMeasurementTool)

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
                self.perf_evaluate_and_report(perf_config, result, baseline=None)

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
                yield PerfConf(perf_tool = self.params.perf_tool,
                               client = client_netns,
                               client_bind = client_bind,
                               server = server_netns,
                               server_bind = server_bind,
                               test_type = perf_test,
                               msg_size = self.params.perf_msg_size,
                               duration = self.params.perf_duration,
                               iterations = self.params.perf_iterations,
                               streams = self.params.perf_streams)

    def _pin_dev_interrupts(self, dev, cpu):
        netns = dev.netns

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
