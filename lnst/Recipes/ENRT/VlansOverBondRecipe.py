from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Devices import VlanDevice
from lnst.Devices.VlanDevice import VlanDevice as Vlan
from lnst.Devices import BondDevice
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints

class VlansOverBondRecipe(VlanPingEvaluatorMixin,
    CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaseEnrtRecipe):
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

        host1.bond0 = BondDevice(mode=self.params.bonding_mode,
            miimon=self.params.miimon_value)
        for dev in [host1.eth0, host1.eth1]:
            dev.down()
            host1.bond0.slave_add(dev)

        host1.vlan0 = VlanDevice(realdev=host1.bond0, vlan_id=10)
        host1.vlan1 = VlanDevice(realdev=host1.bond0, vlan_id=20)
        host1.vlan2 = VlanDevice(realdev=host1.bond0, vlan_id=30)
        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=10)
        host2.vlan1 = VlanDevice(realdev=host2.eth0, vlan_id=20)
        host2.vlan2 = VlanDevice(realdev=host2.eth0, vlan_id=30)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []
        for host in [host1, host2]:
            configuration.test_wide_devices.extend([host.vlan0,
                host.vlan1, host.vlan2])
        configuration.test_wide_devices.append(host1.bond0)

        net_addr = "192.168"
        net_addr6 = "fc00:0:0"

        for i, host in enumerate([host1, host2]):
            host.vlan0.ip_add(ipaddress(net_addr + '.10' + '.' + str(i+1)
                + "/24"))
            host.vlan0.ip_add(ipaddress(net_addr6 + ":1::" + str(i+1) +
                "/64"))
            host.vlan1.ip_add(ipaddress(net_addr + '.20' + '.' + str(i+1) +
                "/24"))
            host.vlan1.ip_add(ipaddress(net_addr6 + ":2::" + str(i+1) +
                "/64"))
            host.vlan2.ip_add(ipaddress(net_addr + '.30' + '.' + str(i+1) +
                "/24"))
            host.vlan2.ip_add(ipaddress(net_addr6 + ":3::" + str(i+1) +
                "/64"))

        for dev in [host1.eth0, host1.eth1, host1.bond0, host1.vlan0,
            host1.vlan1, host1.vlan2, host2.eth0, host2.vlan0,
            host2.vlan1, host2.vlan2]:
            dev.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        return configuration

    def generate_test_wide_description(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                "Configured {}.{}.ips = {}".format(
                    dev.host.hostid, dev.name, dev.ips
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in config.test_wide_devices if isinstance(dev,
                    Vlan)
            ]),
            "Configured {}.{}.slaves = {}".format(
                host1.hostid, host1.bond0.name,
                ['.'.join([host1.hostid, slave.name])
                for slave in host1.bond0.slaves]
            ),
            "Configured {}.{}.mode = {}".format(
                host1.hostid, host1.bond0.name,
                host1.bond0.mode
            ),
            "Configured {}.{}.miimon = {}".format(
                host1.hostid, host1.bond0.name,
                host1.bond0.miimon
            )
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        host1, host2 = self.matched.host1, self.matched.host2
        result = []
        for src in [host1.vlan0, host1.vlan1, host1.vlan2]:
            for dst in [host2.vlan0, host2.vlan1, host2.vlan2]:
                result += [PingEndpoints(src, dst,
                    reachable=(src.vlan_id == dst.vlan_id))]
        return result

    def generate_perf_endpoints(self, config):
        return [(self.matched.host1.vlan0, self.matched.host2.vlan0)]

    @property
    def offload_nics(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        result = []
        for host in [host1, host2]:
            for dev in [host.vlan0, host.vlan1, host.vlan2]:
                result.append(dev)
        result.extend([host1.bond0, host2.eth0])
        return result

    @property
    def coalescing_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        host1, host2 = self.matched.host1, self.matched.host2
        return [host1.eth0, host1.eth1, host2.eth0]
