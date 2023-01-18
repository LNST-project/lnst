import logging
from itertools import product
from lnst.Common.Parameters import (
    Param,
    IntParam,
    StrParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.VirtualEnrtRecipe import VirtualEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Recipes.ENRT.PingMixins import VlanPingEvaluatorMixin
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import OvsBridgeDevice

class VirtualOvsBridgeVlansOverBondRecipe(VlanPingEvaluatorMixin,
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

    vlan0_id = IntParam(default=10)
    vlan1_id = IntParam(default=20)

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

    vlan0_ipv4 = IPv4NetworkParam(default="192.168.10.0/24")
    vlan0_ipv6 = IPv6NetworkParam(default="fc00:0:0:1::/64")

    vlan1_ipv4 = IPv4NetworkParam(default="192.168.20.0/24")
    vlan1_ipv6 = IPv6NetworkParam(default="fc00:0:0:2::/64")

    bonding_mode = StrParam(mandatory = True)
    miimon_value = IntParam(mandatory = True)

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)

        for host, port_name in [(host1, "bond_port1"),
            (host2, "bond_port2")]:
            for dev in [host.eth0, host.eth1, host.tap0, host.tap1]:
                dev.down()
            host.br0 = OvsBridgeDevice()
            host.br0.port_add(device=host.tap0, port_options={'tag': self.params.vlan0_id})
            host.br0.port_add(device=host.tap1, port_options={'tag': self.params.vlan1_id})
            #miimon cannot be set due to colon in argument name -->
            #other_config:bond-miimon-interval
            host.br0.bond_add(port_name, (host.eth0, host.eth1),
                bond_mode=self.params.bonding_mode)

        guest1.eth0.down()
        guest2.eth0.down()
        guest3.eth0.down()
        guest4.eth0.down()

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [guest1.eth0, guest2.eth0,
            guest3.eth0, guest4.eth0]

        vlan0_ipv4_addr = interface_addresses(self.params.vlan0_ipv4)
        vlan0_ipv6_addr = interface_addresses(self.params.vlan0_ipv6)
        vlan1_ipv4_addr = interface_addresses(self.params.vlan1_ipv4)
        vlan1_ipv6_addr = interface_addresses(self.params.vlan1_ipv6)

        for guest in [guest1, guest3]:
            guest.eth0.ip_add(next(vlan0_ipv4_addr))
            guest.eth0.ip_add(next(vlan0_ipv6_addr))

        for guest in [guest2, guest4]:
            guest.eth0.ip_add(next(vlan1_ipv4_addr))
            guest.eth0.ip_add(next(vlan1_ipv6_addr))

        for host in [host1, host2]:
            for dev in [host.eth0, host.eth1, host.tap0, host.tap1,
                host.br0]:
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
                "Configured {}.{}.ports = {}".format(
                    dev.host.hostid, dev.name, dev.ports
                )
                for dev in [host1.br0, host2.br0]
            ]),
            "\n".join([
                "Configured {}.{}.bonds = {}".format(
                    dev.host.hostid, dev.name, dev.bonds
                )
                for dev in [host1.br0, host2.br0]
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
            for dev in [host.eth0, host.eth1, host.tap0, host.tap1,
                host.br0]:
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
