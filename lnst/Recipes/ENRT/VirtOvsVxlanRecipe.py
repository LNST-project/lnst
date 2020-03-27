from itertools import combinations
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.Devices import OvsBridgeDevice

class VirtOvsVxlanRecipe(CommonHWSubConfigMixin, BaseEnrtRecipe):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
    host1.tap0 = DeviceReq(label="to_guest1")
    host1.tap1 = DeviceReq(label="to_guest2")

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))
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

    def test_wide_configuration(self):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)

        for host in [host1, host2]:
            host.eth0.down()
            host.tap0.down()
            host.tap1.down()
        for guest in [guest1, guest2, guest3, guest4]:
            guest.eth0.down()

        net_addr = "192.168.2"
        vxlan_net_addr = "192.168.100"
        vxlan_net_addr6 = "fc00:0:0:0"

        flow_entries=[]
        flow_entries.append("table=0,in_port=5,actions=set_field:100->"
            "tun_id,output:10")
        flow_entries.append("table=0,in_port=6,actions=set_field:200->"
            "tun_id,output:10")
        flow_entries.append("table=0,in_port=10,tun_id=100,actions="
            "output:5")
        flow_entries.append("table=0,in_port=10,tun_id=200,actions="
            "output:6")
        flow_entries.append("table=0,priority=100,actions=drop")

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.eth0, host2.eth0,
            guest1.eth0, guest2.eth0, guest3.eth0, guest4.eth0]

        for i, host in enumerate([host1, host2]):
            host.eth0.ip_add(ipaddress(net_addr + "." + str(i+1) + "/24"))
            host.br0 = OvsBridgeDevice()
            for dev, ofport_r in [(host.tap0, '5'), (host.tap1, '6')]:
                host.br0.port_add(dev, set_iface=True,
                    ofport_request=ofport_r)
            tunnel_opts = {"option:remote_ip" : net_addr + "." + str(2-i),
                "option:key" : "flow", "ofport_request" : '10'}
            host.br0.tunnel_add("vxlan", tunnel_opts)
            host.br0.flows_add(flow_entries)
            for dev in [host.eth0, host.tap0, host.tap1, host.br0]:
                dev.up()

        for i, guest in enumerate([guest1, guest2, guest3, guest4]):
            guest.eth0.ip_add(ipaddress(vxlan_net_addr + "." + str(i+1) +
                "/24"))
            guest.eth0.ip_add(ipaddress(vxlan_net_addr6 + "::" + str(i+1) +
                "/64"))
            guest.eth0.up()

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
                "Configured {}.{}.tunnels = {}".format(
                    dev.host.hostid, dev.name, dev.tunnels
                )
                for dev in [host1.br0, host2.br0]
            ]),
            "\n".join([
                "Configured {}.{}.flows = {}".format(
                    dev.host.hostid, dev.name, dev.flows_str
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
        devs = [guest1.eth0, guest2.eth0, guest3.eth0, guest4.eth0]
        return combinations(devs, 2)

    def generate_perf_endpoints(self, config):
        return [(self.matched.guest1.eth0, self.matched.guest3.eth0)]

    def wait_tentative_ips(self, devices):
        def condition():
            return all(
                [not ip.is_tentative for dev in devices for ip in dev.ips]
            )

        self.ctl.wait_for_condition(condition, timeout=5)

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.guest1.eth0, self.matched.guest2.eth0,
            self.matched.guest3.eth0, self.matched.guest4.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    def do_ping_tests(self, recipe_config):
        for ping_config in self.generate_ping_configurations(recipe_config):
            exp_fail = []
            for pconf in ping_config:
                cond = self.tun_id_match(pconf.client_bind,
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

    def tun_id_match(self, src_addr, dst_addr):
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

    def hw_config(self, config):
        host1, host2, guest1, guest2, guest3, guest4 = (self.matched.host1,
            self.matched.host2, self.matched.guest1, self.matched.guest2,
            self.matched.guest3, self.matched.guest4)

        config.hw_config = {}
        hw_config = config.hw_config

        if "dev_intr_cpu" in self.params:
            intr_cfg = hw_config["dev_intr_cpu_configuration"] = {}
            intr_cfg["irq_devs"] = {}
            intr_cfg["irqbalance_hosts"] = []

            for host in [host1, host2, guest1, guest2, guest3, guest4]:
                host.run("service irqbalance stop")
                intr_cfg["irqbalance_hosts"].append(host)

            for dev in [host1.eth0, host2.eth0]:
                self._pin_dev_interrupts(dev, self.params.dev_intr_cpu)
                intr_cfg["irq_devs"][dev] = self.params.dev_intr_cpu
