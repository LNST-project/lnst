from typing import Literal, Optional
from socket import AF_INET, AF_INET6

from lnst.Common.IpAddress import BaseIpAddress
from lnst.Devices import RemoteDevice


class EnrtConfiguration:
    """Container object for configuration

    Stores configured devices and IPs configured on them. Can also be
    used to store any values relevant to configuration being applied
    during the lifetime of the Recipe.
    """
    def __init__(self):
        self._device_ips = {}

    @property
    def configured_devices(self) -> list[RemoteDevice]:
        return list(self._device_ips.keys())

    def ips_for_device(
        self, device: RemoteDevice, family: Optional[Literal[AF_INET, AF_INET6]] = None
    ) -> list[BaseIpAddress]:
        if family is None:
            return self._device_ips[device]
        return [ip for ip in self._device_ips[device] if ip.family == family]

    def track_device(self, device: RemoteDevice) -> None:
        self._device_ips.setdefault(device, [])

    def untrack_device(self, device: RemoteDevice) -> None:
        del self._device_ips[device]

    def configure_and_track_ip(
        self,
        device: RemoteDevice,
        ip_address: BaseIpAddress,
        peer: Optional[BaseIpAddress] = None,
    ) -> None:
        """Configure IP for device and"""
        device.ip_add(ip_address, peer=peer)
        self._device_ips.setdefault(device, []).append(ip_address)
