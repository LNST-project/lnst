from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Devices import VlanDevice

class VlansRecipe(CommonHWSubConfigMixin, OffloadSubConfigMixin,
    BaseEnrtRecipe):
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

        host1.eth0.down()
        host2.eth0.down()

        host1.vlan0 = VlanDevice(realdev=host1.eth0, vlan_id=10)
        host1.vlan1 = VlanDevice(realdev=host1.eth0, vlan_id=20)
        host1.vlan2 = VlanDevice(realdev=host1.eth0, vlan_id=30)
        host2.vlan0 = VlanDevice(realdev=host2.eth0, vlan_id=10)
        host2.vlan1 = VlanDevice(realdev=host2.eth0, vlan_id=20)
        host2.vlan2 = VlanDevice(realdev=host2.eth0, vlan_id=30)

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = []
        for host in [host1, host2]:
            configuration.test_wide_devices.extend([host.vlan0, host.vlan1,
                host.vlan2])

        net_addr = "192.168"
        net_addr6 = "fc00:0:0"

        for i, host in enumerate([host1, host2]):
            host.vlan0.ip_add(ipaddress(net_addr + '.10' + '.' + str(i+1) +
                "/24"))
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
            for dev in [host.eth0, host.vlan0, host.vlan1, host.vlan2]:
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
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.vlan_id = {}".format(
                    dev.host.hostid, dev.name, dev.vlan_id
                )
                for dev in config.test_wide_devices
            ]),
            "\n".join([
                "Configured {}.{}.realdev = {}".format(
                    dev.host.hostid, dev.name,
                    '.'.join([dev.host.hostid, dev.realdev.name])
                )
                for dev in config.test_wide_devices
            ])
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

    def wait_tentative_ips(self, devices):
        def condition():
            return all(
                [not ip.is_tentative for dev in devices for ip in dev.ips]
            )

        self.ctl.wait_for_condition(condition, timeout=5)

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def mtu_hw_config_dev_list(self):
        result = []
        for host in [self.matched.host1, self.matched.host2]:
            for dev in [host.eth0, host.vlan0, host.vlan1, host.vlan2]:
                result.append(dev)
        return result

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    def do_ping_tests(self, recipe_config):
        for ping_config in self.generate_ping_configurations(
            recipe_config):
            exp_fail = []
            for pconf in ping_config:
                cond = self.vlan_id_same(pconf.client_bind,
                    pconf.destination_address)
                exp_fail.append(cond)
            result = self.ping_test(ping_config, exp_fail)
            self.ping_evaluate_and_report(result)

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

    def vlan_id_same(self, src_addr, dst_addr):
        host1, host2 = self.matched.host1, self.matched.host2
        devs = []
        for dev in (host1.devices + host2.devices):
            if src_addr in dev.ips or dst_addr in dev.ips:
                devs.append(dev)
        try:
            return devs[0].vlan_id != devs[1].vlan_id
        except (IndexError, AttributeError):
            return False
