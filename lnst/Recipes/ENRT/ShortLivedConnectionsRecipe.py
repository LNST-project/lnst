"""
Implements scenario similar to regression_tests/phase3/
(short_lived_connections.xml + short_lived_connections.py)
"""
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Common.Parameters import Param, IntParam, ListParam

class ShortLivedConnectionsRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    perf_tests = Param(default=("TCP_RR", "TCP_CRR"))
    ip_versions = Param(default=("ipv4",))
    perf_parallel_streams = IntParam(default=2)
    perf_msg_sizes = ListParam(default=[1000, 5000, 7000, 10000, 12000])

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        for host in [host1, host2]:
            host.eth0.down()

        net_addr = "192.168.101"

        for i, host in enumerate([host1, host2], 10):
            host.eth0.ip_add(ipaddress(net_addr + "." + str(i) + "/24"))

        #Due to limitations in the current EnrtConfiguration
        #class, a single vlan test pair is chosen
        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.eth0
        configuration.endpoint2 = host2.eth0

        if "mtu" in self.params:
            for host in [host1, host2]:
                host.eth0.mtu = self.params.mtu

        for host in [host1, host2]:
            host.eth0.up()

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
                self._pin_dev_interrupts(host.eth0, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                host.run("tc qdisc replace dev %s root mq" % host.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")

    def generate_ping_configurations(self, main_config, sub_config):
        return []
