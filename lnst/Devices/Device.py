"""
Defines the Device class implementing the common methods for all device types.
Every other device type needs to inherit from this class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re
from abc import ABCMeta
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceError, DeviceDeleted
from lnst.Common.IpAddress import IpAddress

try:
    from pyroute2.netlink.iproute import RTM_NEWLINK
    from pyroute2.netlink.iproute import RTM_NEWADDR
    from pyroute2.netlink.iproute import RTM_DELADDR
except ImportError:
    from pyroute2.iproute import RTM_NEWLINK
    from pyroute2.iproute import RTM_NEWADDR
    from pyroute2.iproute import RTM_DELADDR

#TODO check string parameter values
class Device(object):
    """The base Device class

    Implemented using the pyroute2 package to access different attributes of
    a kernel netdevice object.
    Changing attributes of a netdevice is right now implemented by calling
    shell commands (e.g. from iproute2 package).

    The Controller-Slave communication is implemented in such a way that all
    public methods defined in this and derived class are directly available
    as a tester facing API.
    """
    __metaclass__ = ABCMeta

    def __init__(self, if_manager):
        self.if_index = None #TODO ifindex
        self._nl_msg = None
        self._devlink = None
        self._if_manager = if_manager
        self._enabled = True
        self._deleted = False

        self._ip_addrs = []

    def _create(self):
        """Creates a new netdevice of the corresponding type

        Method to be implemented by derived classes where applicable.
        """
        msg = "Can't create a hardware ethernet device."
        raise DeviceError(msg)

    def _destroy(self):
        """Destroys the netdevice of the corresponding type

        For the basic eth device it calls the destroy method of it's master
        device (if there is one). Flushes the configured IP addresses and sets
        the device 'down'.
        """
        if self.master:
            self.master.destroy()
        self.ip_flush()
        self.down()
        return True

    def _enable(self):
        """Enables the Device object"""
        self._enabled = True

    def _disable(self):
        """Disables the Device object

        When a Device object is disabled, any calls to it's methods will result
        in a "no operation", however attribute access will still work.

        The justification for this is to disable the Device used by the
        Controller-Slave connection to avoid accidental disconnects.
        """
        self._enabled = False

    def __getattribute__(self, name):
        what = object.__getattribute__(self, name)

        if object.__getattribute__(self, "_deleted"):
            raise DeviceDeleted()

        if not callable(what):
            return what
        else:
            if (object.__getattribute__(self, "_enabled") or
                    name in ["enable", "disable"]):
                return what
            else:
                def noop(*args, **kwargs):
                    pass
                return noop

    def _set_devlink(self, devlink_port_data):
        self._devlink = devlink_port_data

    def _init_netlink(self, nl_msg):
        self.if_index = nl_msg['index']

        self._nl_msg = nl_msg

    def _update_netlink(self, nl_msg):
        if self.if_index != nl_msg['index']:
            msg = "if_index of netlink message (%s) doesn't match "\
                  "the device's (%s)." % (nl_msg['index'], self.if_index)
            raise DeviceError(msg)

        if nl_msg['header']['type'] == RTM_NEWLINK:
            if self.if_index != nl_msg['index']:
                raise DeviceError("RTM_NEWLINK message passed to incorrect "\
                                  "Device object.")

            self._nl_msg = nl_msg
        elif nl_msg['header']['type'] == RTM_NEWADDR:
            if self.if_index != nl_msg['index']:
                raise DeviceError("RTM_NEWADDR message passed to incorrect "\
                                  "Device object.")

            addr = IpAddress(nl_msg.get_attr('IFA_ADDRESS'))
            addr.prefixlen = nl_msg["prefixlen"]

            if addr not in self._ip_addrs:
                self._ip_addrs.append(addr)
        elif nl_msg['header']['type'] == RTM_DELADDR:
            if self.if_index != nl_msg['index']:
                raise DeviceError("RTM_DELADDR message passed to incorrect "\
                                  "Device object.")

            addr = IpAddress(nl_msg.get_attr('IFA_ADDRESS'))
            addr.prefixlen = nl_msg["prefixlen"]

            if addr in self._ip_addrs:
                self._ip_addrs.remove(addr)

    @property
    def link_header_type(self):
        """link_header_type attribute

        Returns the integer type of the link layer header as reported by the
        kernel. See ARPHRD constants in /usr/include/linux/if_arp.h.
        """
        return self._nl_msg['ifi_type']

    #TODO jbenc | interface type: IFLA_LINKINFO -> IFLA_INFO_KIND
    #TODO add ifi_flags

    #TODO add setter
    @property
    def name(self):
        """name attribute

        Returns string name of the device as reported by the kernel.
        """
        return self._nl_msg.get_attr("IFLA_IFNAME")

    #TODO add setter
    @property
    def hwaddr(self):
        """hwaddr attribute

        Returns string hardware address of the device as reported by the kernel.
        """
        #TODO implement HwAddress object
        return normalize_hwaddr(self._nl_msg.get_attr("IFLA_ADDRESS"))

    @property
    def state(self):
        """state attribute

        Returns string state of the device as reported by the kernel.
        """
        #TODO check flags for admin up and lower up!!!
        #TODO or expand this to check all possibilities?
        #TODO also, add passive wait until lower up, with timeout
        return self._nl_msg.get_attr("IFLA_OPERSTATE")

    @property
    def ips(self):
        """list of configured ip addresses

        Returns list of BaseIpAddress objects.
        """
        return self._ip_addrs

    #TODO add setter
    @property
    def mtu(self):
        """mtu attribute

        Returns integer mtu as reported by the kernel.
        """
        return self._nl_msg.get_attr("IFLA_MTU")

    @property
    def master(self):
        """master device

        Returns Device object of the master device or None when the device has
        no master.
        """
        master_if_index = self._nl_msg.get_attr("IFLA_MASTER")
        if master_if_index is not None:
            return self._if_manager.get_device(master_if_index)
        else:
            return None

    @master.setter
    def master(self, dev):
        """set dev as the master of this device

        Args:
            dev -- accepts a Device object of the master object.
                When None, removes the current master from the Device."""
        if isinstance(dev, Device):
            exec_cmd("ip link set %s master %s" % (self.name, dev.name))
        elif dev is None:
            exec_cmd("ip link set %s nomaster" % self.name)
        else:
            raise DeviceError("Invalid dev argument.")

    @property
    def driver(self):
        """driver attribute

        Returns string name of the device driver based on an ethtool -i call
        """
        if self.link_header_type == 772:  #loopback ifi type
            return 'loopback'
        out, _ = exec_cmd("ethtool -i %s" % self.name, False, False, False)
        match = re.search("^driver: (.*)$", out, re.MULTILINE)
        if match is not None:
            return match.group(1)
        else:
            return None

    @property
    def link_stats(self):
        """Link statistics

        Returns dictionary of interface statistics, IFLA_STATS
        """
        return self._nl_msg.get_attr("IFLA_STATS")

    @property
    def link_stats64(self):
        """Link statistics

        Returns dictionary of interface statistics, IFLA_STATS64
        """
        return self._nl_msg.get_attr("IFLA_STATS64")

    def _clear_ips(self):
        self._ip_addrs = []

    def _clear_tc_qdisc(self):
        exec_cmd("tc qdisc replace dev %s root pfifo" % self.name)
        out, _ = exec_cmd("tc filter show dev %s" % self.name)
        ingress_handles = re.findall("ingress (\\d+):", out)
        for ingress_handle in ingress_handles:
            exec_cmd("tc qdisc del dev %s handle %s: ingress" %
                     (self.name, ingress_handle))
        out, _ = exec_cmd("tc qdisc show dev %s" % self.name)
        ingress_qdiscs = re.findall("qdisc ingress (\\w+):", out)
        if len(ingress_qdiscs) != 0:
                exec_cmd("tc qdisc del dev %s ingress" % self.name)

    def _clear_tc_filters(self):
        out, _ = exec_cmd("tc filter show dev %s" % self.name)
        egress_prefs = re.findall("pref (\\d+) .* handle", out)

        for egress_pref in egress_prefs:
            exec_cmd("tc filter del dev %s pref %s" % (self.name,
                     egress_pref))

    def ip_add(self, addr):
        """add an ip address

        Args:
            addr -- accepts a BaseIpAddress object
        """
        #TODO support string addr
        ip = IpAddress(addr)
        if addr not in self.ips:
            exec_cmd("ip addr add %s/%d dev %s" % (addr, addr.prefixlen,
                                                   self.name))

    def ip_del(self, addr):
        """remove an ip address

        Args:
            addr -- accepts a BaseIpAddress object
        """
        #TODO support string addr
        if addr in self.ips:
            exec_cmd("ip addr del %s/%d dev %s" % (addr, addr.prefixlen,
                                                   self.name))

    def ip_flush(self):
        """flush all ip addresses of the device"""
        #TODO call flush instead
        for ip in self.ips:
            self.ip_del(ip)

    def up(self):
        """set device up"""
        exec_cmd("ip link set %s up" % self.name)

    def down(self):
        """set device down"""
        exec_cmd("ip link set %s down" % self.name)

    #TODO implement proper Route objects
    # def route_add(self, dest):
        # """add specified route for this device

        # Args:
            # dest -- string accepted by the "ip route add " command
        # """
        # exec_cmd("ip route add %s dev %s" % (dest, self.name))

    # def route_del(self, dest):
        # """remove specified route for this device

        # Args:
            # dest -- string accepted by the "ip route del " command
        # """
        # exec_cmd("ip route del %s dev %s" % (dest, self.name))

    def _get_if_data(self):
        if_data = {"if_index": self.if_index,
                   "hwaddr": self.hwaddr,
                   "name": self.name,
                   "ip_addrs": self.ips,
                   "link_header_type": self.link_header_type,
                   "state": self.state,
                   "master": self.master,
                   "mtu": self.mtu,
                   "driver": self.driver,
                   "devlink": self._devlink}
        return if_data

    def speed_set(self, speed):
        """set the device speed

        Also disables automatic speed negotiation

        Args:
            speed -- string accepted by the 'ethtool -s dev speed ' command
        """
        exec_cmd("ethtool -s %s speed %s" % (self.name, speed))

    def autoneg_on(self):
        """enable automatic negotiation of speed for this device"""
        exec_cmd("ethtool -s %s autoneg on" % self.name)

    def autoneg_off(self):
        """disable automatic negotiation of speed for this device"""
        exec_cmd("ethtool -s %s autoneg off" % self.name)
