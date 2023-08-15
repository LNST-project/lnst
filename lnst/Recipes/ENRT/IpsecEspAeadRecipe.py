import signal
import logging
import copy
from lnst.Common.IpAddress import interface_addresses
from lnst.Common.IpAddress import AF_INET, AF_INET6
from lnst.Common.Parameters import StrParam, IPv4NetworkParam, IPv6NetworkParam
from lnst.Common.LnstError import LnstError
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.BaseSubConfigMixin import (
    BaseSubConfigMixin as ConfMixin)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin)
from lnst.RecipeCommon.PacketAssert import (PacketAssertConf,
                                            PacketAssertTestAndEvaluate)
from lnst.RecipeCommon.Perf.Measurements import Flow as PerfFlow
from lnst.RecipeCommon.Ping.Recipe import PingConf
from lnst.Recipes.ENRT.XfrmTools import (configure_ipsec_esp_aead,
                                         generate_key)


class IpsecEspAeadRecipe(CommonHWSubConfigMixin, BaremetalEnrtRecipe,
                         PacketAssertTestAndEvaluate):
    """
    This recipe implements Enrt testing for a simple IPsec scenario that looks
    as follows

    .. code-block:: none

                    +--------+
             +------+ switch +-----+
             |      +--------+     |
          +--+-+                 +-+--+
        +-|eth0|-+             +-|eth0|-+
        | +----+ |             | +----+ |
        | host1  |             | host2  |
        +--------+             +--------+

    The recipe provides additional recipe parameter to configure IPsec tunel.

        :param ipsec_mode:
            mode of the ipsec tunnel

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="to_switch", driver=RecipeParam("driver"))

    net1_ipv4 = IPv4NetworkParam(default="192.168.99.0/24")
    net1_ipv6 = IPv6NetworkParam(default="fc00:1::/64")
    net2_ipv4 = IPv4NetworkParam(default="192.168.100.0/24")
    net2_ipv6 = IPv6NetworkParam(default="fc00:2::/64")

    algorithm = [('rfc4106(gcm(aes))', 160, 96)]
    spi_values = ["0x00001000", "0x00001001"]
    ipsec_mode = StrParam(default="transport")

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves just adding an IPv4 and
        IPv6 address to the matched eth0 nics on both hosts and route between them.

        host1.eth0 = 192.168.101.1/24 and fc00::1/64

        host2.eth0 = 192.168.101.2/24 and fc00::2/64
        """
        host1, host2 = self.matched.host1, self.matched.host2

        config = super().test_wide_configuration()

        ipv4_addr = {host1: interface_addresses(self.params.net1_ipv4),
                     host2: interface_addresses(self.params.net2_ipv4)}
        ipv6_addr = {host1: interface_addresses(self.params.net1_ipv6),
                     host2: interface_addresses(self.params.net2_ipv6)}
        for host in [host1, host2]:
            host.eth0.down()
            config.configure_and_track_ip(host.eth0, next(ipv4_addr[host]))
            config.configure_and_track_ip(host.eth0, next(ipv6_addr[host]))
            host.eth0.up()

        self.wait_tentative_ips(config.configured_devices)

        if self.params.ping_parallel or self.params.ping_bidirect:
            logging.debug("Parallelism in pings is not supported for this "
                          "recipe, ping_parallel/ping_bidirect will be ignored.")

        for host, dst in [(host1, host2), (host2, host1)]:
            for ip in config.ips_for_device(dst.eth0):
                host.run(f"ip route add {ip} dev {host.eth0.name}")

        config.endpoint1 = host1.eth0
        config.endpoint2 = host2.eth0

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        """
        Test wide description is extended with the configured IP addresses,
        specified IPsec algorithm, key length and integrity check value length.
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join([
                f"Configured {dev.host.hostid}.{dev.name}.ips = {dev.ips}"
                for dev in config.configured_devices
            ]).join([f"Configured IPsec {self.params.ipsec_mode} mode with {algo} algorithm "
                     f"using key length of {key_len} and icv length of {icv_len}"
                     for algo, key_len, icv_len in self.algorithm])

        ]
        return desc

    def test_wide_deconfiguration(self, config):
        super().test_wide_deconfiguration(config)

    def generate_sub_configurations(self, config):
        """
        Test wide configuration is extended with subconfiguration containing
        IPsec tunnel with predefined parameters for both IP versions.
        """
        ipsec_mode = self.params.ipsec_mode
        spi_values = self.spi_values
        for subconf in ConfMixin.generate_sub_configurations(self, config):
            for ipv in self.params.ip_versions:
                family = AF_INET if ipv == "ipv4" else AF_INET6

                ip1 = config.ips_for_device(subconf.endpoint1, family=family)[0]
                ip2 = config.ips_for_device(subconf.endpoint2, family=family)[0]

                for algo, key_len, icv_len in self.algorithm:
                    g_key = generate_key(key_len)
                    new_config = copy.copy(subconf)
                    new_config.ips = (ip1, ip2)
                    new_config.ipsec_settings = (algo, g_key, icv_len,
                                                 ipsec_mode, spi_values)
                    yield new_config

    def apply_sub_configuration(self, config):
        """
        Subconfiguration containing IPsec tunnel is applied through
        XfrmTools class.
        """
        super().apply_sub_configuration(config)
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        ip1, ip2 = config.ips
        ipsec_sets = config.ipsec_settings
        configure_ipsec_esp_aead(ns1, ip1, ns2, ip2, *ipsec_sets)

    def remove_sub_configuration(self, config):
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        for ns in (ns1, ns2):
            ns.run("ip xfrm policy flush")
            ns.run("ip xfrm state flush")
        super().remove_sub_configuration(config)

    def generate_ping_configurations(self, config):
        """
        The ping endpoints for this recipe are the configured endpoints of
        the IPsec tunnel on both hosts.
        """
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        ip1, ip2 = config.ips
        count = self.params.ping_count
        interval = self.params.ping_interval
        size = self.params.ping_psize
        common_args = {'count': count, 'interval': interval,
                       'size': size}
        ping_conf = PingConf(client=ns1,
                             client_bind=ip1,
                             destination=ns2,
                             destination_address=ip2,
                             **common_args)
        yield [ping_conf]

    def generate_flow_combinations(self, config):
        """
        Flow combinations are generated based on the tunnel endpoints
        and test parameters.
        """
        nic1, nic2 = config.endpoint1, config.endpoint2
        ns1, ns2 = config.endpoint1.netns, config.endpoint2.netns
        ip1, ip2 = config.ips
        for perf_test in self.params.perf_tests:
            for size in self.params.perf_msg_sizes:
                flow = PerfFlow(
                    type=perf_test,
                    generator=ns1,
                    generator_bind=ip1,
                    generator_nic=nic1,
                    receiver=ns2,
                    receiver_bind=ip2,
                    receiver_nic=nic2,
                    msg_size=size,
                    duration=self.params.perf_duration,
                    warmup_duration=self.params.perf_warmup_duration,
                    parallel_streams=self.params.perf_parallel_streams,
                    generator_cpupin=self.params.perf_tool_cpu if (
                            "perf_tool_cpu" in self.params) else None,
                    receiver_cpupin=self.params.perf_tool_cpu if (
                            "perf_tool_cpu" in self.params) else None
                )
                yield [flow]

                if ("perf_reverse" in self.params and
                        self.params.perf_reverse):
                    reverse_flow = self._create_reverse_flow(flow)
                    yield [reverse_flow]

    def ping_test(self, ping_configs):
        """
        Ping test is utilizing PacketAssert class to search
        for the appropriate ESP IP packet. Result of ping
        test is handed to the super class' method.

        Returned as::

            (ping_result, pa_config, pa_result)
        """
        m1, m2 = ping_configs[0].client, ping_configs[0].destination
        ip1, ip2 = (ping_configs[0].client_bind,
                    ping_configs[0].destination_address)
        if1_name = self.get_dev_by_ip(m1, ip1).name
        if2 = self.get_dev_by_ip(m2, ip2)

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "esp"
        pa_kwargs["grep_for"] = ['ESP\(spi=' + self.spi_values[1]]
        if ping_configs[0].count:
            pa_kwargs["p_min"] = ping_configs[0].count
        pa_config = PacketAssertConf(m2, if2, **pa_kwargs)

        dump = m1.run("tcpdump -i %s -nn -vv" % if1_name, bg=True)
        self.packet_assert_test_start(pa_config)
        self.ctl.wait(2)
        ping_result = super().ping_test(ping_configs)
        self.ctl.wait(2)
        pa_result = self.packet_assert_test_stop()
        dump.kill(signal=signal.SIGINT)

        return (ping_result, pa_config, pa_result)

    def ping_report_and_evaluate(self, results):
        super().ping_report_and_evaluate(results[0])
        self.packet_assert_evaluate_and_report(results[1], results[2])

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
