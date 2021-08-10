from socket import AF_INET, AF_INET6
from typing import List

from lnst.Common.Parameters import Param
from lnst.Common.IpAddress import ipaddress
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Controller.Host import Host
from lnst.RecipeCommon.MPTCPManager import MPTCPManager
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe


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

    #Only use mptcp
    perf_tests = Param(default=("mptcp_stream",))

    def init_mptcp_control(self, hosts: List[Host]):
        """
        TODO maybe move this to some sort of MPTCPMixin
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
        config.test_wide_devices = []
        config.mptcp_endpoints = []
        hosts = [host1, host2]

        self.init_mptcp_control(hosts)

        for i, host in enumerate(hosts):
            host.run("sysctl -w /net/mptcp/enabled=1")
            host.eth0.ip_add(ipaddress("192.168.101." + str(i+1) + "/24"))
            host.eth1.ip_add(ipaddress("192.168.102." + str(i+1) + "/24"))
            #TODO ASK MPTCP DEVs whats the deal with v6? Can we test it at the same time as v4 or does it have to be a seperate run.
            #host.eth0.ip_add(ipaddress("fc00::" + str(i+1) + "/64"))
            #host.eth1.ip_add(ipaddress("fc01::" + str(i+1) + "/64"))
            host.eth0.up()
            host.eth1.up()
            config.test_wide_devices.append(host.eth0)
            config.test_wide_devices.append(host.eth1)
            config.mptcp_endpoints.append(host.eth1)

        #Configure endpoints
        #TODO Might need to redo this
        # ASK MPTCP DEV we  might not need to configure endpoints on both sides,
        # or if we do the optioons might be different (ie subflows only on client side)
        for ep_dev in config.mptcp_endpoints:
            #TODO check with MPTCP devs about ipv6 support
            ep_dev.netns.mptcp.add_endpoints(ep_dev.ips_filter(family=AF_INET))
            #ep_dev.netns.mptcp.add_endpoints(ep_dev.ips_filter(family=AF_INET6))

        self.wait_tentative_ips(config.test_wide_devices)

        return config


    def generate_test_wide_description(self, config):
        """
        Test wide description is extended with the configured addresses
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            f"Configured {dev.host.hostid}.{dev.name}.ips = {dev.ips}"
            for dev in config.test_wide_devices
        ]

        desc += [f"Configured {dev.host.hostid}.mptcp_endpoints = {dev.ips}"
                 for dev in config.mptcp_endpoints]

        return desc

    def test_wide_deconfiguration(self, config):
        """

        :param config:
        :return:
        """
        for ep_dev in config.test_wide_devices:
            ep_dev.netns.mptcp.delete_all()

        del config.test_wide_devices

        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints are all ports in their respective pairs
        """
        return [PingEndpoints(self.matched.host1.eth0, self.matched.host2.eth0),
                PingEndpoints(self.matched.host1.eth1, self.matched.host2.eth1)]

    def generate_perf_endpoints(self, config):
        """
        Due to the way MPTCP works, the the perf endpoints will be the 2 "primary" ports/flows
        TODO look into other options, to get traffic to traverse the subflow.
        """
        return [(self.matched.host1.eth0, self.matched.host2.eth0)]


    #TODO
    #ASK MPTCP DEVs
    # Do/should we test with the features from the below methods (pause frames, offload, mtu, etc).
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
