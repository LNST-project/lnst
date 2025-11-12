"""
Module implementing InterfaceStatsMonitor test module,
which gathers interface statistics.

Copyright 2025 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
sdobron@redhat.com (Samuel Dobron)
"""


import time
import signal
import logging

from lnst.Tests.BaseTestModule import BaseTestModule, InterruptException
from lnst.Common.Parameters import DeviceParam, FloatParam, ListParam


def sigint_handler(signum, frame):
    raise InterruptException()


class InterfaceStatsMonitor(BaseTestModule):
    """
    Test module for gathering interface statistics on a device.
    Each :attr:`interval` seconds, the module will gather
    stats based on :attr:`stats` list.

    The module runs indefinitely until interrupted by SIGINT signal.

    Only standard netlink stats are supported. Vendor specific
    stats are not supported as these are not exported via netlink.
    If you need them, use ethtool instead.
    """

    device = DeviceParam(mandatory=True)
    interval = FloatParam(default=1.0)
    stats = ListParam(default=["rx_bytes", "tx_bytes", "rx_packets", "tx_packets"])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._res_data = []

    def run(self):
        logging.info(
            f"Gathering stats on device {self.params.device.name} until interrupted"
        )

        raw_samples = []
        old_handler = None
        try:
            old_handler = signal.signal(signal.SIGINT, sigint_handler)
            while True:
                self.params.device._if_manager.rescan_devices()
                # ^ needs to rescan devices to update netlink msg
                # where stats are fetched from

                res = self.params.device.link_stats64

                sample = {"timestamp": time.time()}
                for stat in self.params.stats:
                    sample |= {stat: res[stat]}

                raw_samples.append(sample)
                time.sleep(self.params.interval)
        except InterruptException:
            pass
        finally:
            if old_handler is not None:
                signal.signal(signal.SIGINT, old_handler)

        self._res_data = raw_samples

        return True
