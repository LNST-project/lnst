from lnst.Common.DeviceError import DeviceError
from lnst.Devices.Device import Device
from lnst.Devices.BridgeDevice import BridgeDevice
from lnst.Devices.OvsBridgeDevice import OvsBridgeDevice
from lnst.Devices.BondDevice import BondDevice
from lnst.Devices.TeamDevice import TeamDevice
from lnst.Devices.MacvlanDevice import MacvlanDevice
from lnst.Devices.VlanDevice import VlanDevice
from lnst.Devices.VxlanDevice import VxlanDevice
from lnst.Devices.GreDevice import GreDevice
from lnst.Devices.Ip6GreDevice import Ip6GreDevice
from lnst.Devices.SitDevice import SitDevice
from lnst.Devices.IpIpDevice import IpIpDevice
from lnst.Devices.Ip6TnlDevice import Ip6TnlDevice
from lnst.Devices.VtiDevice import VtiDevice, Vti6Device
from lnst.Devices.VethDevice import VethDevice, PairedVethDevice
from lnst.Devices.VethPair import VethPair
from lnst.Devices.MacsecDevice import MacsecDevice
from lnst.Devices.L2TPSessionDevice import L2TPSessionDevice
from lnst.Devices.RemoteDevice import RemoteDevice, remotedev_decorator

device_classes = [
        ("Device", Device),
        ("BridgeDevice", BridgeDevice),
        ("OvsBridgeDevice", OvsBridgeDevice),
        ("MacvlanDevice", MacvlanDevice),
        ("VlanDevice", VlanDevice),
        ("VxlanDevice", VxlanDevice),
        ("GreDevice", GreDevice),
        ("Ip6GreDevice", Ip6GreDevice),
        ("SitDevice", SitDevice),
        ("IpIpDevice", IpIpDevice),
        ("Ip6TnlDevice", Ip6TnlDevice),
        ("VethDevice", VethDevice),
        ("PairedVethDevice", PairedVethDevice),
        ("VtiDevice", VtiDevice),
        ("Vti6Device", Vti6Device),
        ("BondDevice", BondDevice),
        ("TeamDevice", TeamDevice),
        ("MacsecDevice", MacsecDevice),
        ("L2TPSessionDevice", L2TPSessionDevice)]

for name, cls in device_classes:
    globals()[name] = remotedev_decorator(cls)

#Remove the PairedVethDevice from globals... doesn't make sense to use it on
#it's own, not even for isinstance... VethDevice works fine for that
del globals()["PairedVethDevice"]
