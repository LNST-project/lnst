from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import IntParam, Param, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress, AF_INET, AF_INET6

from lnst.Controller import HostReq, DeviceReq, RecipeParam

from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration

class SimplePerfRecipe(BaseEnrtRecipe):
    m1 = HostReq()
    m1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    m2 = HostReq()
    m2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    def test_wide_configuration(self):
        m1, m2 = self.matched.m1, self.matched.m2

        configuration = EnrtConfiguration()
        configuration.endpoint1 = m1.eth0
        configuration.endpoint2 = m2.eth0

        if "mtu" in self.params:
            m1.eth0.mtu = self.params.mtu
            m2.eth0.mtu = self.params.mtu

        #TODO redo
        # configuration.saved_coalescing_state = dict(
                # m1_if = dict(tx = m1.eth0.adaptive_tx_coalescing,
                             # rx = m1.eth0.adaptive_rx_coalescing),
                # m2_if = dict(tx = m2.eth0.adaptive_tx_coalescing,
                             # rx = m2.eth0.adaptive_rx_coalescing))

        # m1.eth0.adaptive_tx_coalescing = self.params.adaptive_coalescing
        # m1.eth0.adaptive_rx_coalescing = self.params.adaptive_coalescing
        # m2.eth0.adaptive_tx_coalescing = self.params.adaptive_coalescing
        # m2.eth0.adaptive_rx_coalescing = self.params.adaptive_coalescing

        m1.eth0.ip_add(ipaddress("192.168.101.1/24"))
        m1.eth0.ip_add(ipaddress("fc00::1/64"))
        m1.eth0.up()

        m2.eth0.ip_add(ipaddress("192.168.101.2/24"))
        m2.eth0.ip_add(ipaddress("fc00::2/64"))
        m2.eth0.up()

        if "adaptive_rx_coalescing" in self.params:
            for m in [m1, m2]:
                m.eth0.adaptive_rx_coalescing = self.params.adaptive_rx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for m in [m1, m2]:
                m.eth0.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance stop")
                self._pin_dev_interrupts(m.eth0, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for m in [m1, m2]:
                m.run("tc qdisc replace dev %s root mq" % m.eth0.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        m1, m2 = self.matched.m1, self.matched.m2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for m in [m1, m2]:
                m.run("service irqbalance start")

        # redo
        # m1.eth0.adaptive_tx_coalescing = self.saved_coalescing_state["m1_if"]["tx"]
        # m1.eth0.adaptive_rx_coalescing = self.saved_coalescing_state["m1_if"]["rx"]
        # m2.eth0.adaptive_tx_coalescing = self.saved_coalescing_state["m2_if"]["tx"]
        # m2.eth0.adaptive_rx_coalescing = self.saved_coalescing_state["m2_if"]["rx"]
