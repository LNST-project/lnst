from __future__ import annotations
from dataclasses import dataclass, replace as dataclass_replace
from collections.abc import Iterator
from typing import Generic, TypeVar

from lnst.Common.IpAddress import BaseIpAddress
from lnst.Controller.Namespace import Namespace
from lnst.Devices import RemoteDevice


# marked as covariant to allow saving a value of type `IPEndpoint[Ip4Address]`
# to a variable of type `IPEndpoint[BaseIpAddress]`
TIpAddress_co = TypeVar("TIpAddress_co", bound=BaseIpAddress, covariant=True)


@dataclass
class Endpoint:
    """Basic endpoint object.

    The host and device name are derived from a provided device.
    """

    device: RemoteDevice

    @property
    def host(self) -> Namespace:
        return self.device.netns

    @property
    def device_name(self) -> str:
        return self.device.name


@dataclass
class IPEndpoint(Endpoint, Generic[TIpAddress_co]):
    """IP endpoint object"""

    address: TIpAddress_co


@dataclass
class IPPortEndpoint(Generic[TIpAddress_co], IPEndpoint[TIpAddress_co]):
    port: int


# marked as covariant to allow saving a value of type `EndpointPair[IPEndpoint]`
# to a variable of type `EndpointPair[Endpoint]`
TEndpoint_co = TypeVar("TEndpoint_co", bound=Endpoint, covariant=True)


@dataclass
class EndpointPair(Generic[TEndpoint_co]):
    """Represents a pair of endpoints."""

    first: TEndpoint_co
    second: TEndpoint_co

    def __iter__(self) -> Iterator[TEndpoint_co]:
        yield self.first
        yield self.second

    # TODO: replace return type with typing.Self in python3.11
    def reversed(self) -> EndpointPair:
        return dataclass_replace(self, first=self.second, second=self.first)
