from collections.abc import Collection, Iterator
from socket import AF_INET, AF_INET6
from typing import List

from lnst.Common.Parameters import Param, IPv4NetworkParam, IPv6NetworkParam
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.Host import Host
from lnst.RecipeCommon.MPTCPManager import MPTCPManager
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration


from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin,
)

class MPTCPRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, BaremetalEnrtRecipe
):
    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net", driver=RecipeParam("driver"))

    offload_combinations = Param(default=(
        dict(gro="on", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="off", gso="on", tso="on", tx="on", rx="on"),
        dict(gro="on", gso="off", tso="off", tx="on", rx="on"),
        dict(gro="on", gso="on", tso="off", tx="off", rx="on"),
        dict(gro="on", gso="on", tso="on", tx="on", rx="off")))

    net1_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net1_ipv6 = IPv6NetworkParam(default="fc00::/64")
    net2_ipv4 = IPv4NetworkParam(default="192.168.102.0/24")
    net2_ipv6 = IPv6NetworkParam(default="fc01::/64")

    # Only use mptcp
    perf_tests = Param(default=("mptcp_stream",))

    def init_mptcp_control(self, hosts: List[Host]):
        """
        Initialize MPTCP RPC by sending the `MPTCPManager` to each host.
        In the future this might be moved to some sort of `MPTCPMixin`
        :param hosts:
        :return:
        """
        for host in hosts:
            host.mptcp = host.init_class(MPTCPManager)

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves just adding an IPv4 and
        IPv6 address to the matched eth0 nics on both hosts.

        host1.eth0 = 192.168.101.1/24 and fc00::1/64
        host1.eth1 = 192.168.102.1/24 and fc01::1/64


        host2.eth0 = 192.168.101.2/24 and fc00::2/64
        host2.eth1 = 192.168.102.2/24 and fc01::2/64
        """
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration()
        config.mptcp_endpoints = [host1.eth1]
        hosts = [host1, host2]

        self.init_mptcp_control(hosts)

        ipv4_addr1 = interface_addresses(self.params.net1_ipv4)
        ipv6_addr1 = interface_addresses(self.params.net1_ipv6)
        ipv4_addr2 = interface_addresses(self.params.net2_ipv4)
        ipv6_addr2 = interface_addresses(self.params.net2_ipv6)

        save_addrs = {}

        for host in hosts:
            host.run("sysctl -w /net/mptcp/enabled=1")
            config.configure_and_track_ip(host.eth0, next(ipv4_addr1))
            config.configure_and_track_ip(host.eth0, next(ipv6_addr1))
            config.configure_and_track_ip(host.eth1, save_addr4 := next(ipv4_addr2))
            config.configure_and_track_ip(host.eth1, save_addr6 := next(ipv6_addr2))
            save_addrs[host.eth1] = {AF_INET: save_addr4, AF_INET6: save_addr6}

            host.eth0.up()
            host.eth1.up()

        # Configure endpoints only host1.eth1
        if "ipv4" in self.params.ip_versions:
            host1.run(
                f"ip mptcp endpoint add {save_addrs[host1.eth1][AF_INET]}"
                f" dev {host1.eth1.name} subflow"
            )

            # Need route on client side to populate forwarding table
            host1.run(
                f"ip route add {self.params.net1_ipv4} dev {host1.eth1.name}"
                f" via {save_addrs[host2.eth1][AF_INET]} prio 10000"
            )

            # allow hosts to respond to packets on a different interface
            # than the one the packet originated from
            for host in hosts:
                host.run("sysctl -w net.ipv4.conf.all.rp_filter=0")
                host.run(f"sysctl -w net.ipv4.conf.{host.eth0.name}.rp_filter=0")
                host.run(f"sysctl -w net.ipv4.conf.{host.eth1.name}.rp_filter=0")

        if "ipv6" in self.params.ip_versions:
            host1.run(
                f"ip mptcp endpoint add {save_addrs[host1.eth1][AF_INET6]}"
                f" dev {host1.eth1.name} subflow"
            )
            host1.run(
                f"ip route add {self.params.net1_ipv6} dev {host1.eth1.name}"
                f" via {save_addrs[host2.eth1][AF_INET6]} prio 10000"
            )

            # TODO: For IPv6, rp_filter should be disabled via firewalld or ip6tables
            # see https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/7/html/security_guide/sec-securing_network_access#sect-Security_Guide-Server_Security-Reverse_Path_Forwarding

        # set additional mptcp subflows to 1
        host1.mptcp.subflows = 1
        host2.mptcp.subflows = 1

        self.wait_tentative_ips(config.configured_devices)

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        """
        Test wide description is extended with the configured addresses
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            f"Configured {dev.host.hostid}.{dev.name}.ips = {dev.ips}"
            for dev in config.configured_devices
        ]

        desc += [f"Configured {dev.host.hostid}.mptcp_endpoints = {dev.ips}"
                 for dev in config.mptcp_endpoints]

        return desc

    def test_wide_deconfiguration(self, config: EnrtConfiguration) -> None:
        for ep_dev in config.configured_devices:
            ep_dev.netns.mptcp.delete_all()

        # use strict mode
        for host in [self.matched.host1, self.matched.host2]:
            host.run("sysctl -w net.ipv4.conf.all.rp_filter=1")
            host.run(f"sysctl -w net.ipv4.conf.{host.eth0.name}.rp_filter=1")
            host.run(f"sysctl -w net.ipv4.conf.{host.eth1.name}.rp_filter=1")

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints are all ports in their respective pairs
        """
        return [PingEndpoints(self.matched.host1.eth0, self.matched.host2.eth0),
                PingEndpoints(self.matched.host1.eth1, self.matched.host2.eth1)]

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> Iterator[Collection[EndpointPair[IPEndpoint]]]:
        """
        Due to the way MPTCP works, the the perf endpoints will be the 2 "primary" ports/flows
        """
        yield ip_endpoint_pairs(config, (self.matched.host1.eth0, self.matched.host2.eth0))

    #TODO MPTCP Devs would like it to have:
    # eth0.mtu = default
    # eth1.mtu = 8k.
    @property
    def pause_frames_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0, self.matched.host2.eth1]

    @property
    def offload_nics(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0, self.matched.host2.eth1]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0, self.matched.host2.eth1]

    @property
    def coalescing_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0, self.matched.host2.eth1]

    @property
    def dev_interrupt_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0, self.matched.host2.eth1]

    @property
    def parallel_stream_qdisc_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host1.eth1,
                self.matched.host2.eth0, self.matched.host2.eth1]
