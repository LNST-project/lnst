import os
import psutil
import logging
from typing import Literal, Union
from ipaddress import IPv4Network, IPv6Network, IPv4Address, IPv6Address

from ..IpAddress import BaseIpAddress
from .WaitForConditionModule import WaitForConditionModule


class WaitForEstablishedConnections(WaitForConditionModule):
    def __init__(
        self,
        destination_net: Union[IPv4Network, IPv6Network],
        stream: str,
        total_connections: int,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._kind = self.get_kind(destination_net, stream)
        self._total_connections = total_connections

        self._destination = destination_net

    @staticmethod
    def get_kind(destination, stream):
        """
        Converts tcp_{stream,crr,...} (self.params.perf_tests) 
        IPv4 or 6 network (self.params.ip_versions) to tcp4, tcp6, udp4, udp6.
        """
        kind = "tcp"
        if "udp" in stream:
            kind = "udp"

        if isinstance(destination, IPv4Network):
            kind += "4"
        else:
            kind += "6"

        return kind

    def _condition(self):
        connections = psutil.net_connections(kind=self._kind)
        addr_family = (
            IPv4Address if isinstance(self._destination, IPv4Network) else IPv6Address
        )

        filtered = filter(
            lambda conn: addr_family(conn.laddr.ip) in self._destination, connections
        )

        establised_connections = len(list(filtered))
        logging.debug(
            f"Established connections: {establised_connections} / {self._total_connections}"
        )

        return establised_connections >= self._total_connections
