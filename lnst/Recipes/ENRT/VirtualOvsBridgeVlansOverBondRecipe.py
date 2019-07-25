import logging
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWConfigMixin import (
    CommonHWConfigMixin)
from lnst.Devices import OvsBridgeDevice

class VirtualOvsBridgeVlansOverBondRecipe(OffloadSubConfigMixin,
    CommonHWConfigMixin, BaseEnrtRecipe):
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

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on"),
        dict(gro="off", gso="on", tso="on", tx="on"),
        dict(gro="on", gso="off", tso="off", tx="on"),
        dict(gro="on", gso="on", tso="off", tx="off")))

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
            for dev, tag in [(host.tap0, "10"), (host.tap1, "20")]:
                host.br0.port_add(dev, tag=tag)
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

        net_addr_1 = "192.168.10"
        net_addr6_1 = "fc00:0:0:1"
        net_addr_2 = "192.168.20"
        net_addr6_2 = "fc00:0:0:2"

        for i, guest in enumerate([guest1, guest3]):
            guest.eth0.ip_add(ipaddress(net_addr_1 + "." + str(i+1) +
                "/24"))
            guest.eth0.ip_add(ipaddress(net_addr6_1 + "::" + str(i+1) +
                "/64"))

        for i, guest in enumerate([guest2, guest4]):
            guest.eth0.ip_add(ipaddress(net_addr_2 + "." + str(i+1) +
                "/24"))
            guest.eth0.ip_add(ipaddress(net_addr6_2 + "::" + str(i+1) +
                "/64"))

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
        return [(guest1.eth0, guest3.eth0), (guest4.eth0, guest2.eth0),
            (guest1.eth0, guest4.eth0), (guest3.eth0, guest2.eth0)]

    def generate_perf_endpoints(self, config):
        return [(self.matched.guest1.eth0, self.matched.guest3.eth0)]

    def wait_tentative_ips(self, devices):
        def condition():
            return all(
                [not ip.is_tentative for dev in devices for ip in dev.ips]
            )

        self.ctl.wait_for_condition(condition, timeout=5)

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

    def do_ping_tests(self, recipe_config):
        for ping_config in self.generate_ping_configurations(
            recipe_config):
            exp_fail = []
            for pconf in ping_config:
                cond = self.vlan_id_match(pconf.client_bind,
                    pconf.destination_address)
                exp_fail.append(cond)
            result = self.ping_test(ping_config, exp_fail)
            self.ping_evaluate_and_report(ping_config, result)

    def ping_test(self, ping_config, exp_fail):
        results = {}

        running_ping_array = []
        for pingconf, fail in zip(ping_config, exp_fail):
            ping, client = self.ping_init(pingconf)
            running_ping = client.prepare_job(ping, fail=fail)
            running_ping.start(bg = True)
            running_ping_array.append((pingconf, running_ping))

        for _, pingjob in running_ping_array:
            try:
                pingjob.wait()
            finally:
                pingjob.kill()

        for pingconf, pingjob in running_ping_array:
            result = pingjob.result
            passed = pingjob.passed
            results[pingconf] = (result, passed)

        return results

    def single_ping_evaluate_and_report(self, ping_config, result):
        fmt = "From: <{0.client.hostid} ({0.client_bind})> To: " \
              "<{0.destination.hostid} ({0.destination_address})>"
        description = fmt.format(ping_config)
        if result[0].get("rate", 0) > 50:
            message = "Ping successful --- " + description
            self.add_result(result[1], message, result[0])
        else:
            message = "Ping unsuccessful --- " + description
            self.add_result(result[1], message, result[0])

    def vlan_id_match(self, src_addr, dst_addr):
        guest1, guest2, guest3, guest4 = (self.matched.guest1,
            self.matched.guest2, self.matched.guest3, self.matched.guest4)

        matching_pairs = []
        for pair in [(guest1, guest3), (guest2, guest4)]:
            matching_pairs.extend([pair, pair[::-1]])

        devs = []
        for dev in (guest1.devices + guest2.devices + guest3.devices +
                    guest4.devices):
            if src_addr in dev.ips or dst_addr in dev.ips:
                devs.append(dev)
        try:
            return (devs[0].host, devs[1].host) not in matching_pairs
        except IndexError:
            return False
