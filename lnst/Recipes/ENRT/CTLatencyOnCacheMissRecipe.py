import logging
import socket
import time
from .CTInsertionRateNftablesRecipe import CTInsertionRateNftablesRecipe
from .ConfigMixins.LongLivedConnectionsMixin import LongLivedConnectionsMixin
from math import ceil

from lnst.Tests.LongLivedConnections import LongLivedServer, LongLivedClient
from lnst.Common.IpAddress import interface_addresses
from lnst.Common.Parameters import IntParam
from lnst.Common.Parameters import IPv4NetworkParam, IPv6NetworkParam
from lnst.Common.conditions.WaitForEstablishedConnections import (
    WaitForEstablishedConnections,
)
from lnst.Recipes.ENRT.MeasurementGenerators.LatencyMeasurementGenerator import (
    LatencyMeasurementGenerator,
)


class CTLatencyOnCacheMissRecipe(
    LatencyMeasurementGenerator,
    LongLivedConnectionsMixin,
    CTInsertionRateNftablesRecipe,
):
    @property
    def cache_poison_tool(self) -> callable:
        return self.open_bg_conns

    def open_bg_conns(self, recipe_conf):
        """
        Function opens `long_lived_connections` number of long-lived connections
        that should force CPU to replace cached pages with latency measurement
        connection by these new connections, so another measurement will be cache
        miss.
        """
        recipe_conf.long_lived_connections = []

        for client_job, server_job in self.generate_jobs(recipe_conf):
            recipe_conf.long_lived_connections.append((client_job, server_job))

            server_job.start(bg=True)
            time.sleep(1)
            client_job.start(bg=True)

        logging.info("Waiting for long-lived connections to establish")
        self.wait_for_long_lived_connections()

        logging.info("Long-lived connections established, closing them")
        self.stop_jobs(recipe_conf)

    def generate_perf_configurations(self, config):
        # skip setting up jobs by LongLivedConnectionsMixin
        return super(LongLivedConnectionsMixin, self).generate_perf_configurations(
            config
        )

    def apply_perf_test_tweak(self, config):
        # skip opening long-lived connections by LongLivedConnectionsMixin
        # that's already done by our cache_poison_tool
        return super(LongLivedConnectionsMixin, self).apply_perf_test_tweak(config)

    def remove_perf_test_tweak(self, config):
        # skip closing long-lived connections by LongLivedConnectionsMixin
        # that's already done by our cache_poison_tool
        return super(LongLivedConnectionsMixin, self).remove_perf_test_tweak(config)
