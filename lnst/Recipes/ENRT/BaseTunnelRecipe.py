from collections.abc import Collection

from lnst.Devices import RemoteDevice
from lnst.RecipeCommon.endpoints import EndpointPair, IPEndpoint
from lnst.Recipes.ENRT.helpers import ip_endpoint_pairs
from lnst.Recipes.ENRT.BaremetalEnrtRecipe import BaremetalEnrtRecipe
from lnst.RecipeCommon.PacketAssert import PacketAssertTestAndEvaluate
from lnst.Recipes.ENRT.BaseEnrtRecipe import EnrtConfiguration


class BaseTunnelRecipe(
    PacketAssertTestAndEvaluate,
    BaremetalEnrtRecipe,
):
    """
    This base class extends the :any:`BaseEnrtRecipe` class and defines
    a common API for implementation of baremetal tunnel recipes.

    The :meth:`ping_test` method is overridden to include a test
    that the ping packets are properly tunnelled. This is implemented with
    :any:`PacketAssert` test module. Each child class needs to implement
    :meth:`get_packet_assert_config` so that the correct filters are passed
    to the module.

    The class inheriting from this base class need to implement following
    methods:

    * :meth:`configure_underlying_network`
    * :meth:`create_tunnel`
    * :meth:`get_packet_assert_config`
    """

    def test_wide_configuration(self) -> EnrtConfiguration:
        """
        The base class defines common steps to create the test wide
        configuration of a tunnel recipe.

        First, an underlying network that will be the transport layer for
        the tunnel is configured in :meth:`configure_underlying_network`,
        then the tunnel is created between the specified endpoints in
        :meth:`create_tunnel`.
        """
        config = super().test_wide_configuration()
        config.tunnel_endpoints = self.configure_underlying_network(config)
        config.tunnel_devices = self.create_tunnel(config, config.tunnel_endpoints)
        self.wait_tentative_ips(config.configured_devices)
        return config

    def configure_underlying_network(self, config: EnrtConfiguration) -> tuple[RemoteDevice, RemoteDevice]:
        """
        This method must be implemented by the child class.

        The child class should configure the network stack that will be
        the transport layer for the tunnel configured in :meth:`create_tunnel`.

        That usually includes configuring the IP addresses, creating additional
        network devices such as bonding or vlans, creating network namespaces,
        etc.

        The method must also update the ``tunnel_endpoints`` attribute of the
        ``config`` object with a tuple of two Device objects that will
        be used as tunnel endpoints in :meth:`create_tunnel`

        :param config:
            Used to configure IP addresses and store them inside the config
        :type config: `EnrtConfiguration`

        :return: returns a tuple of two Device objects that will
            be used as tunnel endpoints in :meth:`create_tunnel`
        :rtype: `tuple[RemoteDevice, RemoteDevice]`
        """
        raise NotImplementedError

    def create_tunnel(
        self,
        config: EnrtConfiguration,
        tunnel_endpoints: tuple[RemoteDevice, RemoteDevice],
    ) -> tuple[RemoteDevice, RemoteDevice]:
        """
        This method must be implemented by the child class.

        The child class should create a network tunnel between the provided
        endpoints. That usually includes creating tunnel devices such as
        :any:`GreDevice`, :any:`VxlanDevice`, etc. and configuring the IP addresses.

        :param config:
            Configuration object useful for assigning IP addresses to devices
        :type config: `EnrtConfiguration`

        :param tunnel_endpoints:
            A tuple of the tunnel endpoints.
        :type tunnel_endpoints: `tuple[RemoteDevice, RemoteDevice]`

        :return: A tuple of the configured tunnel devices.
        :rtype: `tuple[RemoteDevice, RemoteDevice]
        """
        raise NotImplementedError

    def generate_test_wide_description(self, config: EnrtConfiguration):
        """
        Test wide description is extended with the configured addresses
        of the underlying network devices and the configured tunnel devices
        """
        desc = super().generate_test_wide_description(config)
        desc += [
            "Configured {}.{}.ips = {}".format(dev.host.hostid, dev.name, dev.ips)
            for dev in config.configured_devices
        ]
        desc += [
            "Configured tunnel endpoint {}.{}.ips = {}".format(
                dev.host.hostid, dev.name, dev.ips
            )
            for dev in config.tunnel_devices
        ]
        return desc

    def ping_test(self, ping_configs):
        pa_config = self.get_packet_assert_config(ping_configs[0])
        self.packet_assert_test_start(pa_config)
        self.ctl.wait(2)
        ping_result = super().ping_test(ping_configs)
        self.ctl.wait(2)
        pa_result = self.packet_assert_test_stop()

        result = ((ping_result, pa_config, pa_result),)

        return result

    def ping_report_and_evaluate(self, results):
        for res in results:
            super().ping_report_and_evaluate(res[0])
            self.packet_assert_evaluate_and_report(res[1], res[2])

    def get_packet_assert_config(self, ping_config):
        """
        This method must be implemented by the child class.

        :param ping_config:
            Ping configuration generated by :meth:`BaseEnrtRecipe.generate_ping_configurations`
        :type ping_config: :any:`PingConfig`

        :return: returns a PacketAssert configuration
        :rtype: :any:`PacketAssertConf`
        """
        raise NotImplementedError

    def generate_perf_endpoints(self, config: EnrtConfiguration) -> list[Collection[EndpointPair[IPEndpoint]]]:
        """
        The perf endpoints for recipes derived from this class are usually
        the tunnel endpoints. The derived class can override the endpoints
        if needed.
        """
        dev1, dev2 = config.tunnel_devices
        return [ip_endpoint_pairs(config, (dev1, dev2))]
