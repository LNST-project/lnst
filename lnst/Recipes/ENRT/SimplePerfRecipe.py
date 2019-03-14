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
        configuration.endpoint1 = host1.eth0
        configuration.endpoint2 = host2.eth0

        if "mtu" in self.params:
            host1.eth0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu

        #TODO redo
        # configuration.saved_coalescing_state = dict(
                # host1_if = dict(tx = host1.eth0.adaptive_tx_coalescing,
                             # rx = host1.eth0.adaptive_rx_coalescing),
                # host2_if = dict(tx = host2.eth0.adaptive_tx_coalescing,
                             # rx = host2.eth0.adaptive_rx_coalescing))

        # host1.eth0.adaptive_tx_coalescing = self.params.adaptive_coalescing
        # host1.eth0.adaptive_rx_coalescing = self.params.adaptive_coalescing
        # host2.eth0.adaptive_tx_coalescing = self.params.adaptive_coalescing
        # host2.eth0.adaptive_rx_coalescing = self.params.adaptive_coalescing

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

        # redo
        # host1.eth0.adaptive_tx_coalescing = self.saved_coalescing_state["host1_if"]["tx"]
        # host1.eth0.adaptive_rx_coalescing = self.saved_coalescing_state["host1_if"]["rx"]
        # host2.eth0.adaptive_tx_coalescing = self.saved_coalescing_state["host2_if"]["tx"]
        # host2.eth0.adaptive_rx_coalescing = self.saved_coalescing_state["host2_if"]["rx"]
