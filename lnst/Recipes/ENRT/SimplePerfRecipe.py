from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import IntParam, Param, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress, AF_INET, AF_INET6

from lnst.Controller import HostReq, DeviceReq, RecipeParam

from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration

class SimplePerfRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        configuration = EnrtConfiguration()
        configuration.params = self.params

        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu

        host1.eth0.ip_add(ipaddress("192.168.101.1/24"))
        host1.eth0.ip_add(ipaddress("fc00::1/64"))
        host1.eth0.up()

        host2.eth0.ip_add(ipaddress("192.168.101.2/24"))
        host2.eth0.ip_add(ipaddress("fc00::2/64"))
        host2.eth0.up()

        if "adaptive_rx_coalescing" in self.params:
            for host in [host1, host2]:
                host.eth0.adaptive_rx_coalescing = self.params.adaptive_rx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for host in [host1, host2]:
                host.eth0.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                host.run("tc qdisc replace dev %s root mq" % host.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

    def generate_ping_endpoints(self, config):
        return [(self.matched.host1.eth0, self.matched.host2.eth0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.eth0, self.matched.host2.eth0)]
