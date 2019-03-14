"""
Implements scenario similar to regression_tests/phase2/
({active_backup,round_robin}_team.xml + team_test.py)
"""
from lnst.Common.Parameters import Param, IntParam, StrParam, BoolParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe, EnrtConfiguration
from lnst.Devices import TeamDevice

class TeamRecipe(BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="tnet")
    host1.eth1 = DeviceReq(label="tnet")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="tnet")

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    perf_reverse = BoolParam(default=True)
    runner_name = StrParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        host1.eth0.down()
        host1.eth1.down()
        #The config argument needs to be used with a team device normally (e.g  to specify
        #the runner mode), but it is not used here due to a bug in the TeamDevice module
        host1.team0 = TeamDevice()
        host1.team0.slave_add(host1.eth0)
        host1.team0.slave_add(host1.eth1)

        #EnrtConfiguration and both-side Netperf config need to be checked
        configuration = EnrtConfiguration()
        configuration.endpoint1 = host1.team0
        configuration.endpoint2 = host2.eth0

        if "mtu" in self.params:
            host1.team0.mtu = self.params.mtu
            host2.eth0.mtu = self.params.mtu

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"

        host1.team0.ip_add(ipaddress(net_addr_1 + ".1/24"))
        host1.team0.ip_add(ipaddress(net_addr6_1 + "::1/64"))
        host2.eth0.ip_add(ipaddress(net_addr_1 + ".2/24"))
        host2.eth0.ip_add(ipaddress(net_addr6_1 + "::2/64"))

        host1.eth0.up()
        host1.eth1.up()
        host1.team0.up()
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
