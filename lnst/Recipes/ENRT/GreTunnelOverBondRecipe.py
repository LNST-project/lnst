from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Common.IpAddress import (
    AF_INET,
    ipaddress,
    Ip4Address,
    Ip6Address,
)
from lnst.Common.Parameters import Param, IntParam, StrParam
from lnst.Devices import GreDevice, BondDevice
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.RecipeCommon.PacketAssert import PacketAssertConf
from lnst.Recipes.ENRT.BaseTunnelRecipe import BaseTunnelRecipe
from lnst.Recipes.ENRT.ConfigMixins.OffloadSubConfigMixin import (
    OffloadSubConfigMixin,
)
from lnst.Recipes.ENRT.ConfigMixins.CommonHWSubConfigMixin import (
    CommonHWSubConfigMixin,
)


class GreTunnelOverBondRecipe(
    CommonHWSubConfigMixin, OffloadSubConfigMixin, BaseTunnelRecipe
):
    """
    This class implements a recipe that configures a GRE tunnel between
    two hosts that are connected through a bond device.

    .. code-block:: none

                         .--------.
              .------.---| switch |---.------.
              |      |   '--------'   |      |
              |      |                |      |
         .----|-- ---|----.      .----|-- ---|----.
         | .--'-.  .-'--. |      | .--'-.  .-'--. |
         | |eth0|  |eth1| |      | |eth0|  |eth1| |
         | '----'  '----' |      | '----'  '----' |
         |     \    /     |      |     \    /     |
         |   .--\--/-.    |      |   .--\--/-.    |
         |   | bond0 |    |      |   | bond0 |    |
         |   '-------'    |      |   '-------'    |
         |      | |       |      |      | |       |
         |   ---' '----   |      |   ---' '----   |
         |   gre tunnel   |      |   gre tunnel   |
         |   ----------   |      |   ----------   |
         |                |      |                |
         |    host1       |      |    host1       |
         '----------------'      '----------------'

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.

    The test wide configuration is implemented in the :any:`BaseTunnelRecipe`
    class.

    The recipe provides additional parameter:

        :param bonding_mode:
            (mandatory test parameter) the bonding mode to be configured on
            the bond0 device.
        :param miimon_value:
            (mandatory test parameter) the miimon interval to be configured
            on the bond0 device.
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)
    offload_combinations = Param(
        default=(
            dict(gro="on", gso="on", tso="on"),
            dict(gro="off", gso="on", tso="on"),
            dict(gro="on", gso="off", tso="off"),
            dict(gro="on", gso="on", tso="off"),
        )
    )

    def configure_underlying_network(self, configuration):
        """
        The underlying network for the tunnel consists of two Ethernet
        devices bonded together by bonding device on both of the matched
        hosts.
        """
        host1, host2 = self.matched.host1, self.matched.host2

        host1.bond = BondDevice(
            mode=self.params.bonding_mode, miimon=self.params.miimon_value
        )
        host2.bond = BondDevice(
            mode=self.params.bonding_mode, miimon=self.params.miimon_value
        )

        for host, devices in [
            (host1, [host1.eth0, host1.eth1]),
            (host2, [host2.eth0, host2.eth1]),
        ]:
            for dev in devices:
                dev.down()
                host.bond.slave_add(dev)

        for i, device in enumerate([host1.bond, host2.bond]):
            device.ip_add(ipaddress("192.168.101." + str(i + 1) + "/24"))
            configuration.test_wide_devices.append(device)

        for dev in [
            host1.eth0,
            host1.eth1,
            host1.bond,
            host2.eth0,
            host2.eth0,
            host2.bond,
        ]:
            dev.up()

        configuration.tunnel_endpoints = (host1.bond, host2.bond)

    def create_tunnel(self, configuration):
        """
        The GRE tunnel devices are configured with local and remote ip addresses
        matching the bond device IP addresses.

        The GRE tunnel devices are configured with IPv4 and IPv6 addresses
        of individual networks. Routes are configured accordingly.
        """
        endpoint1, endpoint2 = configuration.tunnel_endpoints
        m1 = endpoint1.netns
        m2 = endpoint2.netns
        ip_filter = {"family": AF_INET}
        endpoint1_ip = endpoint1.ips_filter(**ip_filter)[0]
        endpoint2_ip = endpoint2.ips_filter(**ip_filter)[0]

        a_ip4 = Ip4Address("192.168.6.2/24")
        a_net4 = "192.168.6.0/24"
        b_ip4 = Ip4Address("192.168.7.2/24")
        b_net4 = "192.168.7.0/24"

        a_ip6 = Ip6Address("6001:db8:ac10:fe01::2/64")
        a_net6 = "6001:db8:ac10:fe01::0/64"
        b_ip6 = Ip6Address("7001:db8:ac10:fe01::2/64")
        b_net6 = "7001:db8:ac10:fe01::0/64"

        m1.gre_tunnel = GreDevice(local=endpoint1_ip, remote=endpoint2_ip)
        m2.gre_tunnel = GreDevice(local=endpoint2_ip, remote=endpoint1_ip)

        # A
        m1.gre_tunnel.up()
        m1.gre_tunnel.ip_add(a_ip4)
        m1.gre_tunnel.ip_add(a_ip6)
        m1.run("ip -4 route add {} dev {}".format(b_net4, m1.gre_tunnel.name))
        m1.run("ip -6 route add {} dev {}".format(b_net6, m1.gre_tunnel.name))

        # B
        m2.gre_tunnel.up()
        m2.gre_tunnel.ip_add(b_ip4)
        m2.gre_tunnel.ip_add(b_ip6)
        m2.run("ip -4 route add {} dev {}".format(a_net4, m2.gre_tunnel.name))
        m2.run("ip -6 route add {} dev {}".format(a_net6, m2.gre_tunnel.name))

        configuration.tunnel_devices.extend([m1.gre_tunnel, m2.gre_tunnel])
        self.wait_tentative_ips(configuration.tunnel_devices)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are simply the tunnel endpoints

        Returned as::

            [PingEndpoints(self.matched.host1.gre_tunnel, self.matched.host2.gre_tunnel)]
        """
        return [
            PingEndpoints(self.matched.host1.gre_tunnel, self.matched.host2.gre_tunnel)
        ]

    def get_packet_assert_config(self, ping_config):
        """
        The packet assert test configuration contains filter for gre protocol
        and grep patterns to match the ICMP or ICMP6 echo requests.
        """
        ip_filter = {"family": AF_INET}
        m1_carrier = self.matched.host1.bond
        m2_carrier = self.matched.host2.bond
        m1_carrier_ip = m1_carrier.ips_filter(**ip_filter)[0]
        m2_carrier_ip = m2_carrier.ips_filter(**ip_filter)[0]

        ip1 = ping_config.client_bind
        ip2 = ping_config.destination_address

        pa_kwargs = {}
        pa_kwargs["p_filter"] = "proto gre"

        if isinstance(ip2, Ip4Address):
            pat1 = "{} > {}: GREv0, .* IP {} > {}: ICMP echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            pat2 = "{} > {}: GREv0 \| {} > {}: ICMP echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            grep_pattern = ["({})|({})".format(pat1, pat2)]
        elif isinstance(ip2, Ip6Address):
            pat1 = "{} > {}: GREv0, .* IP6 {} > {}: ICMP6, echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            pat2 = "{} > {}: GREv0 \| {} > {}: ICMP6, echo request".format(
                m1_carrier_ip, m2_carrier_ip, ip1, ip2
            )
            grep_pattern = ["({})|({})".format(pat1, pat2)]
        else:
            raise Exception("The destination address is nor IPv4 or IPv6 address")

        pa_kwargs["grep_for"] = grep_pattern

        if ping_config.count:
            pa_kwargs["p_min"] = ping_config.count
        m2 = ping_config.destination
        pa_config = PacketAssertConf(m2, m2_carrier, **pa_kwargs)

        return pa_config

    @property
    def offload_nics(self):
        return [self.matched.host1.bond, self.matched.host2.bond]
