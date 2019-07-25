import signal
import logging
import copy
from lnst.Common.IpAddress import ipaddress
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.Parameters import StrParam
from lnst.Common.LnstError import LnstError
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaseEnrtRecipe import BaseEnrtRecipe
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import (
    BaseSubConfigMixin as ConfMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWConfigMixin import (
    CommonHWConfigMixin)
from lnst.RecipeCommon.PacketAssert import (PacketAssertConf,
    PacketAssertTestAndEvaluate)
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Ping import PingConf
from lnst.Recipes.ENRT.XfrmTools import (configure_ipsec_esp_ah_comp,
    generate_key)

class IpsecEspAhCompRecipe(CommonHWConfigMixin, BaseEnrtRecipe,
    PacketAssertTestAndEvaluate):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    ciphers = [('aes', 128), ('aes', 256)]
    hashes = [('hmac(md5)', 128), ('sha256', 256)]
    spi_values = ["0x00000001", "0x00000002", "0x00000003", "0x00000004"]
    ipsec_mode = StrParam(default="transport")

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2

        configuration = super().test_wide_configuration()
        configuration.test_wide_devices = [host1.eth0, host2.eth0]

        net_addr = "192.168."
        net_addr6 = "fc00:"
        for i, host in enumerate([host1, host2]):
            host.eth0.down()
            host.eth0.ip_add(ipaddress(net_addr + str(i+99) + ".1/24"))
            host.eth0.ip_add(ipaddress(net_addr6 + str(i+1) + "::1/64"))
            host.eth0.up()

        self.wait_tentative_ips(configuration.test_wide_devices)

        if self.params.ping_parallel or self.params.ping_bidirect:
            logging.debug("Parallelism in pings is not supported for this"
                "recipe, ping_parallel/ping_bidirect will be ignored.")

        for host, dst in [(host1, host2), (host2, host1)]:
            for family in [AF_INET, AF_INET6]:
                host.run("ip route add %s dev %s" %
                    (dst.eth0.ips_filter(family=family)[0],
                        host.eth0.name))

        configuration.endpoint1 = host1.eth0
        configuration.endpoint2 = host2.eth0

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
            ])
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def wait_tentative_ips(self, devices):
        def condition():
            return all(
                [not ip.is_tentative for dev in devices for ip in dev.ips]
            )

        self.ctl.wait_for_condition(condition, timeout=5)

    def generate_sub_configurations(self, config):
        ipsec_mode = self.params.ipsec_mode
        spi_values = self.spi_values
        for subconf in ConfMixin.generate_sub_configurations(self, config):
            for ipv in self.params.ip_versions:
                if ipv == "ipv4":
                    family = AF_INET
                elif ipv == "ipv6":
                    family = AF_INET6

                ip1 = config.endpoint1.ips_filter(family=family)[0]
                ip2 = config.endpoint2.ips_filter(family=family)[0]

                for ciph_alg, ciph_len in self.ciphers:
                    for hash_alg, hash_len in self.hashes:
                        ciph_key = generate_key(ciph_len)
                        hash_key = generate_key(hash_len)
                        new_config = copy.copy(subconf)
                        new_config.ips = (ip1, ip2)
                        new_config.ipsec_settings = (ciph_alg,
                            ciph_key, hash_alg, hash_key, ipsec_mode,
                            spi_values)
                        yield new_config

    def apply_sub_configuration(self, config):
        super().apply_sub_configuration(config)
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        ip1, ip2 = config.ips
        ipsec_sets = config.ipsec_settings
        configure_ipsec_esp_ah_comp(ns1, ip1, ns2, ip2, *ipsec_sets)

    def remove_sub_configuration(self, config):
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        for ns in (ns1, ns2):
            ns.run("ip xfrm policy flush")
            ns.run("ip xfrm state flush")
        super().remove_sub_configuration(config)

    def generate_ping_configurations(self, config):
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        ip1, ip2 = config.ips
        count = self.params.ping_count
        interval = self.params.ping_interval
        size = self.params.ping_psize
        common_args = {'count' : count, 'interval' : interval,
            'size' : size}
        ping_conf = PingConf(client = ns1,
                             client_bind = ip1,
                             destination = ns2,
                             destination_address = ip2,
                             **common_args)
        yield [ping_conf]

    def generate_flow_combinations(self, config):
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        ip1, ip2 = config.ips
        for perf_test in self.params.perf_tests:
            for size in self.params.perf_msg_sizes:
                flow = PerfFlow(
                    type = perf_test,
                    generator = ns1,
                    generator_bind = ip1,
                    receiver = ns2,
                    receiver_bind = ip2,
                    msg_size = size,
                    duration = self.params.perf_duration,
                    parallel_streams = self.params.perf_parallel_streams,
                    cpupin = self.params.perf_tool_cpu if (
                        "perf_tool_cpu" in self.params) else None
                    )
                yield [flow]

                if ("perf_reverse" in self.params and
                    self.params.perf_reverse):
                    reverse_flow = self._create_reverse_flow(flow)
                    yield [reverse_flow]

    def ping_test(self, ping_config):
        m1, m2 = ping_config[0].client, ping_config[0].destination
        ip1, ip2 = (ping_config[0].client_bind,
            ping_config[0].destination_address)
        if1_name = self.get_dev_by_ip(m1, ip1).name
        if2 = self.get_dev_by_ip(m2, ip2)

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "ah"
        pa_kwargs["grep_for"] = ["AH\(spi=" + self.spi_values[2],
            "ESP\(spi=" + self.spi_values[1]]
        if ping_config[0].count:
            pa_kwargs["p_min"] = 2 * ping_config[0].count
        pa_config = PacketAssertConf(m2, if2, **pa_kwargs)

        dump = m1.run("tcpdump -i %s -nn -vv" % if1_name, bg=True)
        self.packet_assert_test_start(pa_config)
        self.ctl.wait(2)
        ping_result = super().ping_test(ping_config)
        self.ctl.wait(2)
        pa_result = self.packet_assert_test_stop()
        dump.kill(signal=signal.SIGINT)

        m1.run("ip -s xfrm pol")
        m1.run("ip -s xfrm state")

        dump2 = m1.run("tcpdump -i %s -nn -vv" % if1_name, bg=True)
        no_trans = self.params.ipsec_mode != 'transport'
        ping_config2 = copy.copy(ping_config)
        ping_config2[0].size = 1500
        if no_trans:
            pa_kwargs2 = copy.copy(pa_kwargs)
            pa_kwargs2["p_filter"] = ''
            pa_kwargs2["grep_for"] = ["IPComp"]
            if ping_config2[0].count:
                pa_kwargs2["p_min"] = ping_config2[0].count
            pa_config2 = PacketAssertConf(m2, if2, **pa_kwargs2)
            self.packet_assert_test_start(pa_config2)
        self.ctl.wait(2)
        ping_result2 = super().ping_test(ping_config2)
        self.ctl.wait(2)
        if no_trans:
            pa_result2 = self.packet_assert_test_stop()
        dump2.kill(signal=signal.SIGINT)

        result = ((ping_result, pa_config, pa_result),)
        if no_trans:
            result += ((ping_result2, pa_config2, pa_result2),)
        return result

    def ping_evaluate_and_report(self, ping_config, result):
        for res in result:
            super().ping_evaluate_and_report(ping_config, res[0])
            self.packet_assert_evaluate_and_report(res[1], res[2])

    def get_dev_by_ip(self, netns, ip):
        for dev in netns.device_database:
            if ip in dev.ips:
                return dev
        raise LnstError("Could not match ip %s to any device of %s." %
            (ip, netns.name))

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
