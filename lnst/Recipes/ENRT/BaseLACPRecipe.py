from lnst.Common.Parameters import (
    IntParam,
    StrParam,
    DictParam
)
from lnst.Devices import BondDevice
from lnst.Common.IpAddress import interface_addresses
from lnst.Recipes.ENRT.DoubleBondRecipe import DoubleBondRecipe


class BaseLACPRecipe(DoubleBondRecipe):
    bonding_mode = StrParam(mandatory=True)
    miimon_value = IntParam(mandatory=True)

    lacp_mode = StrParam(default="ACTIVE", choices=["ACTIVE", "PASSIVE", "ON"])
    topology = DictParam(mandatory=True)
    """
    Topology should be in following format:
    ```
    {
        "SWITCH_LACP_INTERFACE": [
            "INTERFACE1",
            "INTERFACE2"
        ]
    }
    ```
    """

    def test_wide_switch_configuration(self):
        """
        This method needs to implement switch configuration for LACP.
        """
        raise NotImplementedError()

    def test_wide_configuration(self):
        """
        This method is almost the same as DoubleBondRecipe.test_wide_configuration,
        however, it configures multiple IP addresses on the bond0 interface as well as
        it calls switch configuration method.
        """
        host1, host2 = self.matched.host1, self.matched.host2
        config = super().test_wide_configuration()

        ipv4_addr = interface_addresses(self.params.net_ipv4)
        ipv6_addr = interface_addresses(self.params.net_ipv6)
        for host in [host1, host2]:
            host.bond0 = BondDevice(mode=self.params.bonding_mode,
                                    miimon=self.params.miimon_value)
            host.bond0.xmit_hash_policy = "layer2+3"

            for dev in [host.eth0, host.eth1]:
                dev.down()
                host.bond0.slave_add(dev)

            config.configure_and_track_ip(host.bond0, next(ipv4_addr))
            config.configure_and_track_ip(host.bond0, next(ipv4_addr))

            config.configure_and_track_ip(host.bond0, next(ipv6_addr))
            config.configure_and_track_ip(host.bond0, next(ipv6_addr))

            for dev in [host.eth0, host.eth1, host.bond0]:
                dev.up()

        self.test_wide_switch_configuration()

        self.wait_tentative_ips(config.configured_devices)

        return config

    def test_wide_switch_deconfiguration(self):
        raise NotImplementedError()

    def test_wide_deconfiguration(self, config):
        self.test_wide_switch_deconfiguration()

        super().test_wide_deconfiguration(config)
