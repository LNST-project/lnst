from lnst.Common.Parameters import (
    IntParam,
    StrParam,
    IPv4NetworkParam,
    IPv6NetworkParam,
)
from lnst.Common.IpAddress import interface_addresses
from lnst.Controller import HostReq, DeviceReq, RecipeParam
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.RecipeCommon.Ping.PingEndpoints import PingEndpoints
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration
from lnst.Recipes.ENRT.ConfigMixins.MTUHWConfigMixin import MTUHWConfigMixin
from lnst.Devices import BondDevice, BridgeDevice
from lnst.Devices.BridgeDevice import BridgeDevice as BridgeDeviceType
from lnst.Devices.BondDevice import BondDevice as BondDeviceType


class LinuxBridgeOverBondRecipe(MTUHWConfigMixin, BaremetalEnrtRecipe):
    """
    This recipe implements Enrt testing for a network scenario that looks
    as follows

    .. code-block:: none

             .----------------------------------------.
             |                switch                  |
             '----------------------------------------'
              |        |                    |        |
          .---'--. .---'--.             .---'--. .---'--.
        .-| eth0 |-| eth1 |-.        .-| eth0 |-| eth1 |-.
        | '------' '------' |        | '------' '------' |
        |       \   /       |        |       \   /       |
        |       bond0       |        |       bond0       |
        |         |         |        |         |         |
        |        br0        |        |        br0        |
        |                   |        |                   |
        |       host1       |        |       host2       |
        '-------------------'        '-------------------'

    All sub configurations are included via Mixin classes.

    The actual test machinery is implemented in the :any:`BaseEnrtRecipe` class.
    """

    host1 = HostReq()
    host1.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host1.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    host2 = HostReq()
    host2.eth0 = DeviceReq(label="net1", driver=RecipeParam("driver"))
    host2.eth1 = DeviceReq(label="net1", driver=RecipeParam("driver"))

    net_ipv4 = IPv4NetworkParam(default="192.168.101.0/24")
    net_ipv6 = IPv6NetworkParam(default="fc00::/64")

    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    def test_wide_configuration(self):
        """
        Test wide configuration for this recipe involves
        * creating a bonding device from the matched NICs
        * adding the bonding device into a Linux bridge
        * adding an IPv4 and IPv6 address on the bridge device

        host1.br0 = 192.168.101.1/24 and fc00::1/64

        host2.br0 = 192.168.101.2/24 and fc00::2/64
        """
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)

        for host in [host1, host2]:
            host.bond0 = BondDevice(
                mode=self.params.bonding_mode, miimon=self.params.miimon_value
            )
            for dev in [host.eth0, host.eth1]:
                dev.down()
                host.bond0.slave_add(dev)

            host.br0 = BridgeDevice()
            host.bond0.down()
            host.br0.slave_add(host.bond0)

            for dev in [host.eth0, host.eth1, host.bond0, host.br0]:
                dev.up_and_wait()

            config.configure_and_track_ip(host.br0, next(ipv4_addr))
            config.configure_and_track_ip(host.br0, next(ipv6_addr))
            config.track_device(host.bond0)

        self.wait_tentative_ips(config.configured_devices)

        return config

    def generate_test_wide_description(self, config: EnrtConfiguration):
        """
        Test wide description is extended with the configured addresses
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            "\n".join(
                [
                    "Created bond device {} on host {}".format(
                        dev.name,
                        dev.host.hostid,
                    )
                    for dev in config.configured_devices if isinstance(dev, BondDeviceType)
                ]
            ),
            "\n".join(
                [
                    "Created bridge device {} on host {}".format(
                        dev.name,
                        dev.host.hostid,
                    )
                    for dev in config.configured_devices if isinstance(dev, BridgeDeviceType)
                ]
            ),
            "\n".join(
                [
                    "Added device {} to bridge device {} on host {}".format(
                        dev.name,
                        br_dev.name,
                        dev.host.hostid,
                    )
                    for br_dev in config.configured_devices
                    for dev in br_dev.slaves if isinstance(br_dev, BridgeDeviceType)
                ]
            ),
            "\n".join(
                [
                    "Configured {}.{}.ips = {}".format(
                        dev.host.hostid, dev.name, dev.ips
                    )
                    for dev in config.configured_devices if isinstance(dev, BridgeDeviceType)
                ]
            ),
        ]
        return desc

    def test_wide_deconfiguration(self, config):
        """"""  # overriding the parent docstring
        super().test_wide_deconfiguration(config)

    def generate_ping_endpoints(self, config):
        """
        The ping endpoints for this recipe are the created bridge devices:

        host1.br0 and host2.br0

        Returned as::

            [PingEndpoints(self.matched.host1.br0, self.matched.host2.br0)]
        """
        return [PingEndpoints(self.matched.host1.br0, self.matched.host2.br0)]

    def generate_perf_endpoints(self, config):
        """
        The perf endpoints for this recipe are the created bridge devices:

        host1.br0 and host2.br0

        Returned as::

            [(self.matched.host1.br0, self.matched.host2.br0)]
        """
        return [(self.matched.host1.br0, self.matched.host2.br0)]

    @property
    def mtu_hw_config_dev_list(self):
        return [self.matched.host1.eth0, self.matched.host2.eth0]
