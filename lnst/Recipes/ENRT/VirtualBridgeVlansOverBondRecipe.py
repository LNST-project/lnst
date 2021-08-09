import logging
from itertools import product
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice
from lnst.Devices import BondDevice
from lnst.Devices import BridgeDevice

class VirtualBridgeVlansOverBondRecipe(VlanPingEvaluatorMixin,
    CommonHWSubConfigMixin, OffloadSubConfigMixin, VirtualEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")
    host1.tap1 = DeviceReq(label="to_guest2")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host2.tap0 = DeviceReq(label="to_guest3")
    host2.tap1 = DeviceReq(label="to_guest4")

    guest1 = HostReq()
    guest1.eth0 = DeviceReq(label="to_guest1")

    guest2 = HostReq()
    guest2.eth0 = DeviceReq(label="to_guest2")

    guest3 = HostReq()
    guest3.eth0 = DeviceReq(label="to_guest3")

    guest4 = HostReq()
    guest4.eth0 = DeviceReq(label="to_guest4")

    vlan_ids = Param(default=[10, 20])

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)

        for host in [host1, host2]:
            for dev in [host.eth0, host.eth1, host.tap0, host.tap1]:
                dev.down()
            host.bond0 = BondDevice(mode=self.params.bonding_mode,
                             miimon=self.params.miimon_value)
            host.bond0.slave_add(host.eth0)
            host.bond0.slave_add(host.eth1)
            host.br0 = BridgeDevice()
            host.br0.slave_add(host.tap0)
            host.br1 = BridgeDevice()
            host.br1.slave_add(host.tap1)

        for guest in (guest1, guest2, guest3, guest4):
            guest.eth0.down()

        host1.vlan0 = VlanDevice(realdev=host1.bond0, vlan_id=self.params.vlan_ids[0],
            master=host1.br0)
        host1.vlan1 = VlanDevice(realdev=host1.bond0, vlan_id=self.params.vlan_ids[1],
            master=host1.br1)
        host2.vlan0 = VlanDevice(realdev=host2.bond0, vlan_id=self.params.vlan_ids[0],
            master=host2.br0)
        host2.vlan1 = VlanDevice(realdev=host2.bond0, vlan_id=self.params.vlan_ids[1],
            master=host2.br1)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.br0, host2.br0,
            guest1.eth0, guest2.eth0, guest3.eth0, guest4.eth0]

        net_addr = "192.168"
        net_addr6 = "fc00:0:0"
        for host, (guest_a, guest_b), n in [(host1, (guest1, guest2), 1),
            (host2, (guest3, guest4), 3)]:
            host.br0.ip_add(ipaddress(net_addr + ".10." + str(n) + "/24"))
            host.br1.ip_add(ipaddress(net_addr + ".20." + str(n) + "/24"))
            guest_a.eth0.ip_add(ipaddress(net_addr + ".10." + str(n+1) +
                "/24"))
            guest_a.eth0.ip_add(ipaddress(net_addr6 + ":1::" + str(n+1) +
                "/64"))
            guest_b.eth0.ip_add(ipaddress(net_addr + ".20." + str(n+1) +
                "/24"))
            guest_b.eth0.ip_add(ipaddress(net_addr6 + ":2::" + str(n+1) +
                "/64"))

        for host in [host1, host2]:
            for dev in [host.eth0, host.eth1, host.tap0, host.tap1,
                host.bond0, host.vlan0, host.vlan1, host.br0, host.br1]:
                dev.up()
        for guest in [guest1, guest2, guest3, guest4]:
            guest.eth0.up()

        if "perf_tool_cpu" in self.params:
            logging.info("'perf_tool_cpu' param (%d) to be set to None" %
                self.params.perf_tool_cpu)
            self.params.perf_tool_cpu = None

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
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.slaves = {}".format(
                    dev.host.hostid, dev.name,
                    ['.'.join([dev.host.hostid, slave.name])
                    for slave in dev.slaves]
                )
                for dev in [host1.bond0, host2.bond0, host1.br0,
                    host1.br1, host2.br0, host2.br1]
            ]),
            "\n".join([
                "Configured {}.{}.mode = {}".format(
                    dev.host.hostid, dev.name, dev.mode
                )
                for dev in [host1.bond0, host2.bond0]
            ]),
            "\n".join([
                "Configured {}.{}.miimon = {}".format(
                    dev.host.hostid, dev.name, dev.miimon
                )
                for dev in [host1.bond0, host2.bond0]
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in [host1.vlan0, host1.vlan1,
                    host2.vlan0, host2.vlan1]
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in [host1.vlan0, host1.vlan1, host2.vlan0,
                    host2.vlan1]
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        guest1, guest2, guest3, guest4 = (self.matched.guest1,
            self.matched.guest2, self.matched.guest3, self.matched.guest4)
        dev_combinations = product(
            [guest1.eth0, guest2.eth0],
            [guest3.eth0, guest4.eth0]
            )
        return [
            PingEndpoints(
                comb[0], comb[1],
                reachable=((comb[0].host, comb[1].host) in [
                    (guest1, guest3),
                    (guest2, guest4)
                    ])
                )
                for comb in dev_combinations
            ]

    def generate_perf_endpoints(self, config):
        return [(self.matched.guest1.eth0, self.matched.guest3.eth0)]

    @property
    def offload_nics(self):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)
        result = []
        for machine in host1, host2, guest1, guest2, guest3, guest4:
            result.append(machine.eth0)
        result.extend([host1.eth1, host2.eth1])
        return result

    @property
    def mtu_hw_config_dev_list(self):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)
        result = []
        for host in [host1, host2]:
            for dev in [host.bond0, host.tap0, host.tap1, host.br0,
                host.br1, host.vlan0, host.vlan1]:
                result.append(dev)
        for guest in [guest1, guest2, guest3, guest4]:
            result.append(guest.eth0)
        return result

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0, self.matched.host2.eth1]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
            self.matched.host2.eth0, self.matched.host2.eth1]
