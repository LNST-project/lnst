import time
import signal
import logging
from math import ceil

from lnst.Tests.LongLivedConnections import LongLivedServer, LongLivedClient
from lnst.Common.IpAddress import interface_addresses
from lnst.Common.Parameters import IntParam
from lnst.Common.Parameters import IPv4NetworkParam, IPv6NetworkParam
from lnst.Common.conditions.WaitForEstablishedConnections import (
    WaitForEstablishedConnections,
)
from lnst.RecipeCommon.Perf.PerfTestMixins.BasePerfTestTweakMixin import (
    BasePerfTestTweakMixin,
)


class LongLivedConnectionsMixin(BasePerfTestTweakMixin):
    """
    This mixin adds support for long-lived connections.

    Based on `long_lived_conns` parameter, it will create a number of
    long-lived connections between the hosts. Receiver is a server, while
    generator is a client.

    Only long lived connections IPs are handled by this mixin.
    Therefore, if your test requires perf IPs, it should be
    configured by parent's test_wide_configuration() method.
    IPs used for long-lived client and server are added based on
    long_lived_conns_per_ip parameter, which defines size of
    addressable space for connections. Sinde L4 can address up
    to 65535 ports, it's obviously limited by that. Parameters
    long_lived_conns_net4 and long_lived_conns_net6 are required
    to define IP address space for connections.

    Connections are not equally distributed among clients.
    The first client (and others) will get long_lived_conns_per_ip
    connections, while the last one will get the remaining connections.

    Don't forget to set appropriate system-wide NO_FILES ulimit (if needed).
    See LongLivedServer/LongLivedClient for more details.
    """

    long_lived_conns = IntParam(mandatory=True)
    long_lived_conns_port = IntParam(default=20000)
    long_lived_conns_per_ip = IntParam(default=20000)
    long_lived_conns_net4 = IPv4NetworkParam(default="192.168.102.0/24", mandatory=True)
    long_lived_conns_net6 = IPv6NetworkParam(default="fc01::/64", mandatory=True)

    def test_wide_configuration(self):
        host1, host2 = self.matched.host1, self.matched.host2
        host1.eth0.keep_addrs_on_down()
        host2.eth0.keep_addrs_on_down()

        config = super().test_wide_configuration()
        # L4 can address up to 65535 ports (size of addresable space
        # defined in long_lived_conns_per_ip) Therefore opening connections
        # may require multiple IPs.

        ipv4_addr = interface_addresses(self.params.long_lived_conns_net4)
        ipv6_addr = interface_addresses(self.params.long_lived_conns_net6)
        config.long_lived_ips = {
            host1: {"ipv4": [], "ipv6": []},
            host2: {"ipv4": [], "ipv6": []},
        }

        host1.eth0.down()
        host2.eth0.down()
        for host in [host1, host2]:
            for _ in range(self.servers_count):
                ipv4 = next(ipv4_addr)
                ipv6 = next(ipv6_addr)

                host.eth0.ip_add(ipv4)
                host.eth0.ip_add(ipv6)
                config.long_lived_ips[host]["ipv4"].append(ipv4)
                config.long_lived_ips[host]["ipv6"].append(ipv6)

        host1.eth0.up()
        host2.eth0.up()

        self.wait_tentative_ips(config.configured_devices)

        return config

    def test_wide_deconfiguration(self, config):
        host1, host2 = self.matched.host1, self.matched.host2

        host1.eth0.remove_addrs_on_down()
        host2.eth0.remove_addrs_on_down()

        return super().test_wide_deconfiguration(config)

    @property
    def servers_count(self):
        return ceil(self.params.long_lived_conns / self.params.long_lived_conns_per_ip)

    def generate_perf_configurations(self, config):
        for parent_config in super().generate_perf_configurations(config):
            parent_config.long_lived_connections = []

            for client_job, server_job in self.generate_jobs(config):
                parent_config.long_lived_connections.append((client_job, server_job))

            yield parent_config

    def generate_jobs(self, config):
        for ip_version in self.params.ip_versions:
            host1, host2 = self.matched.host1, self.matched.host2
            filtered_ips = zip(
                config.long_lived_ips[host1][ip_version],
                config.long_lived_ips[host2][ip_version],
            )

            for i, endpoint_pair in enumerate(filtered_ips):
                generator_ip, receiver_ip = endpoint_pair

                connections_count = self.calculate_client_connections(i)

                server_job = self._prepare_server(
                    host2.eth0, receiver_ip, connections_count
                )
                client_job = self._prepare_client(
                    host1.eth0, receiver_ip, generator_ip, connections_count
                )

                yield client_job, server_job

    def calculate_client_connections(self, client_id):
        client_id += 1  # 0-based index
        if client_id < self.servers_count:
            return self.params.long_lived_conns_per_ip

        opened_connections = (
            self.servers_count - 1
        ) * self.params.long_lived_conns_per_ip

        # remaining connections are handled by last client
        return self.params.long_lived_conns - opened_connections

    def _prepare_server(self, receiver_nic, receiver_ip, conns_count):
        server = LongLivedServer(
            server_ip=receiver_ip,
            server_port=self.params.long_lived_conns_port,
            connections_count=conns_count,
        )

        job = receiver_nic.netns.prepare_job(server)

        return job

    def _prepare_client(self, generator_nic, receiver_ip, generator_ip, conns_count):
        client = LongLivedClient(
            server_ip=receiver_ip,
            server_port=self.params.long_lived_conns_port,
            client_ip=generator_ip,
            connections_count=conns_count,
        )

        job = generator_nic.netns.prepare_job(client)

        return job

    def generate_perf_configuration_description(self, config):
        desc = super().generate_perf_configuration_description(config)

        for client_job, server_job in config.long_lived_connections:
            desc.append(
                f"Long-lived connection between {client_job.what} and {server_job.what}"
            )

        return desc

    def apply_perf_test_tweak(self, config):
        super().apply_perf_test_tweak(config)

        for _, server_job in config.long_lived_connections:
            server_job.start(bg=True)

        time.sleep(2)  # just to be sure servers are up

        for client_job, _ in config.long_lived_connections:
            client_job.start(bg=True)

        for version in self.params.ip_versions:
            for stream in self.params.perf_tests:
                addr = (
                    self.params.long_lived_conns_net4
                    if version == "ipv4"
                    else self.params.long_lived_conns_net6
                )

                condition = WaitForEstablishedConnections(
                    addr, stream, self.params.long_lived_conns, timeout=300
                )
                prepared = self.matched.host2.wait_for_condition(condition)

        logging.info("Long-lived connections established")

    def remove_perf_test_tweak(self, config):
        for client_job, server_job in config.long_lived_connections:
            kwargs = {}

            if client_job.what.runtime_estimate():
                kwargs["timeout"] = client_job.what.runtime_estimate()
            else:
                client_job.kill(signal.SIGINT)
                server_job.kill(signal.SIGINT)
                # no timeout defined => it'll use default timer

            try:
                client_job.wait(**kwargs)
                server_job.wait(**kwargs)
            finally:
                client_job.kill()
                server_job.kill()

        del config.long_lived_connections

        return super().remove_perf_test_tweak(config)
