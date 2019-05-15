"""
Implements scenario similar to regression_tests/phase1/
({round_robin, active_backup}_double_bond.xml + bonding_test.py).
"""
from lnst.Common.Parameters import Param, StrParam, IntParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import BondDevice

class DoubleBondRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        for host in (host1, host2):
            host.bond0 = BondDevice(mode=self.params.bonding_mode, miimon=self.params.miimon_value)
            host.eth0.down()
            host.eth1.down()
            host.bond0.slave_add(host.eth0)
            host.bond0.slave_add(host.eth1)

        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.bond0
        configuration.endpoint2 = host2.bond0

        if "mtu" in self.params:
            host1.bond0.mtu = self.params.mtu
            host2.bond0.mtu = self.params.mtu

        net_addr = "192.168.101"
        net_addr6 = "fc00:0:0:0"
        for i, host in enumerate([host1, host2]):
            host.bond0.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            host.bond0.ip_add(ipaddress(net_addr6 + "::" + str(i+1) + "/64"))
            host.eth0.up()
            host.eth1.up()
            host.bond0.up()

        if "adaptive_tx_coalescing" in self.params:
            for host in [host1, host2]:
                for dev in [host.eth0, host.eth1]:
                    dev.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing
        if "adaptive_tx_coalescing" in self.params:
            for host in [host1, host2]:
                for dev in [host.eth0, host.eth1]:
                    dev.adaptive_tx_coalescing = self.params.adaptive_tx_coalescing

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance stop")
                for dev in [host.eth0, host.eth1]:
                    self._pin_dev_interrupts(host.eth0, self.params.dev_intr_cpu)

        if self.params.perf_parallel_streams > 1:
            for host in [host1, host2]:
                for dev in [host.eth0, host.eth1]:
                    host.run("tc qdisc replace dev %s root mq" % dev.name)

        return configuration

    def test_wide_deconfiguration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        #TODO better service handling through HostAPI
        if "dev_intr_cpu" in self.params:
            for host in [host1, host2]:
                host.run("service irqbalance start")
