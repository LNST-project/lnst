"""
Implements scenario similar to regression_tests/phase1/
({active_backup, round_robin}_bond.xml + bonding_test.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import BondDevice

class BondRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        host1.bond0 = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
        host1.eth0.down()
        host1.eth1.down()
        host1.bond0.slave_add(host1.eth0)
        host1.bond0.slave_add(host1.eth1)

        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.bond0
        configuration.endpoint2 = host2.eth0

        if "mtu" in self.params:
            host1.bond0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu

        net_addr = "192.168.101"
        net_addr6 = "fc00:0:0:0"
        host1.bond0.ip_add(ipaddress(net_addr + ".1/24"))
        host1.bond0.ip_add(ipaddress(net_addr6 + "::1/64"))
        host1.eth0.up()
        host1.eth1.up()
        host1.bond0.up()

        host2.eth0.ip_add(ipaddress(net_addr + ".2/24"))
        host2.eth0.ip_add(ipaddress(net_addr6 + "::2/64"))
        host2.eth0.up()

        if "adaptive_rx_coalescing" in self.params:
            for dev in [host1.eth0, host1.eth1, host2.eth0]:
                dev.adaptive_rx_coalescing = self.params.adaptive_rx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for dev in [host1.eth0, host1.eth1, host2.eth0]:
                dev.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
            for dev in [host1.eth0, host1.eth1, host2.eth0]:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for host, dev in [(host1, host1.eth0), (host1, host1.eth1), (host2, host2.eth0)]:
                host.run("tc qdisc replace dev %s root mq" % dev.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")
