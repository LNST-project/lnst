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
import ethtool
import pyroute2
import logging
import pprint
from abc import ABCMeta
from pyroute2.netlink.rtnl import ifinfmsg
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceError, DeviceDeleted, DeviceDisabled
from lnst.Common.DeviceError import DeviceConfigError, DeviceConfigValueError
from lnst.Common.IpAddress import ipaddress
from lnst.Common.HWAddress import hwaddress

try:
    from pyroute2.netlink.iproute import RTM_NEWLINK
    from pyroute2.netlink.iproute import RTM_NEWADDR
    from pyroute2.netlink.iproute import RTM_DELADDR
except ImportError:
    from pyroute2.iproute import RTM_NEWLINK
    from pyroute2.iproute import RTM_NEWADDR
    from pyroute2.iproute import RTM_DELADDR

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
        self.ifindex = None
        self._nl_msg = None
        self._devlink = None
        self._if_manager = if_manager
        self._enabled = True
        self._deleted = False

        self._ip_addrs = []

        self._nl_update = {}
        self._bulk_enabled = False

    def _set_nl_attr(self, msg, value, name):
        msg[name] = value

    def _set_nested_nl_attr(self, msg, value, *args):
        if len(args) == 1:
            self._set_nl_attr(msg, value, args[0])
        elif len(args) > 1:
            if args[0] not in msg:
                msg[args[0]] = {"attrs": {}}
            elif not isinstance(msg[args[0]], dict) or "attrs" not in msg[args[0]]:
                raise DeviceError("Error constructing nested nl msg.")

            attrs = msg[args[0]]["attrs"]
            self._set_nested_nl_attr(attrs, value, *args[1:])
        else:
            raise DeviceError("Error constructing nested nl msg.")

    def _update_attr(self, value, *args):
        self._set_nested_nl_attr(self._nl_update, value, *args)

    def _process_nested_nl_attrs(self, msg):
        ret = {}
        for k, v in msg.items():
            if isinstance(v, dict):
                processed = self._process_nested_nl_attrs(v["attrs"])
                ret[k] = {"attrs": processed.items()}
            else:
                ret[k] = v
        return ret

    def _nl_sync(self, op, ipr_attrs=None, bulk=False):
        if self._bulk_enabled and not bulk:
            return

        if ipr_attrs is None:
            attrs = self._process_nested_nl_attrs(self._nl_update)
        else:
            attrs = self._process_nested_nl_attrs(ipr_attrs)

        with pyroute2.IPRoute() as ipr:
            try:
                pretty_attrs = pprint.pformat(attrs)
                logging.debug("Performing Netlink operation {}, data:".format(op))
                logging.debug("{}".format(pretty_attrs))

                if op == "add":
                    ipr.link(op, **attrs)
                else:
                    ipr.link(op, index=self.ifindex, **attrs)
                self._if_manager.rescan_devices()
            except Exception as e:
                log_exc_traceback()
                raise DeviceConfigError("Operation {} on link {} failed: {}"
                        .format(op, self.name, str(e)))

        if ipr_attrs is None:
            self._nl_update = {}

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
        what = super(Device, self).__getattribute__(name)

        try:
            if super(Device, self).__getattribute__("_deleted"):
                raise DeviceDeleted("Device was deleted.")
        except AttributeError:
            pass

        try:
            if not callable(what):
                return what
            else:
                if (super(Device, self).__getattribute__("_enabled") or
                        name[0] == "_"):
                    return what
                elif not super(Device, self).__getattribute__("_enabled"):
                    raise DeviceDisabled("Can't call methods on a disabled device.")
        except AttributeError:
            return what

    def __setattr__(self, name, value):
        try:
            if getattr(self, "_deleted"):
                raise DeviceDeleted("Device was deleted.")
        except AttributeError:
            pass

        try:
            if not getattr(self, "_enabled") and name[0] != "_":
                raise DeviceDisabled("Can't set attributes for a disabled device.")
        except AttributeError:
            pass

        return super(Device, self).__setattr__(name, value)

    def _set_devlink(self, devlink_port_data):
        self._devlink = devlink_port_data

    def _init_netlink(self, nl_msg):
        self.ifindex = nl_msg['index']

        self._nl_msg = nl_msg
        self._store_cleanup_data()

    def _update_netlink(self, nl_msg):
        if self.ifindex != nl_msg['index']:
            msg = "ifindex of netlink message (%s) doesn't match "\
                  "the device's (%s)." % (nl_msg['index'], self.ifindex)
            raise DeviceError(msg)

        if nl_msg['header']['type'] == RTM_NEWLINK:
            if self.ifindex != nl_msg['index']:
                raise DeviceError("RTM_NEWLINK message passed to incorrect "\
                                  "Device object.")

            self._nl_msg = nl_msg
        elif nl_msg['header']['type'] == RTM_NEWADDR:
            if self.ifindex != nl_msg['index']:
                raise DeviceError("RTM_NEWADDR message passed to incorrect "\
                                  "Device object.")

            addr = ipaddress(nl_msg.get_attr('IFA_ADDRESS'))
            addr.prefixlen = nl_msg["prefixlen"]

            if addr not in self._ip_addrs:
                self._ip_addrs.append(addr)
        elif nl_msg['header']['type'] == RTM_DELADDR:
            if self.ifindex != nl_msg['index']:
                raise DeviceError("RTM_DELADDR message passed to incorrect "\
                                  "Device object.")

            addr = ipaddress(nl_msg.get_attr('IFA_ADDRESS'))
            addr.prefixlen = nl_msg["prefixlen"]

            if addr in self._ip_addrs:
                self._ip_addrs.remove(addr)

    def _get_if_data(self):
        if_data = {"ifindex": self.ifindex,
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

    def _vars(self):
        ret = {}
        for k in dir(self):
            if k[0] == '_':
                continue
            v = getattr(self, k)
            if not callable(v):
                ret[k] = v
        return ret

    def _clear_tc_qdisc(self):
        exec_cmd("tc qdisc del dev %s root" % self.name, die_on_err=False)
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
            exec_cmd("tc filter del dev %s pref %s" % (self.name, egress_pref))

    def _store_cleanup_data(self):
        """Stores initial configuration for later cleanup"""
        self._orig_mtu = self.mtu
        self._orig_name = self.name
        self._orig_hwaddr = self.hwaddr

    def _restore_original_data(self):
        """Restores initial configuration from stored values"""
        if self.mtu != self._orig_mtu:
            self.mtu = self._orig_mtu

        if self.name != self._orig_name:
            self.name = self._orig_name

        if self.hwaddr != self._orig_hwaddr:
            self.hwaddr = self._orig_hwaddr

    def _create(self):
        """Creates a new netdevice of the corresponding type

        Method to be implemented by derived classes where applicable.
        """
        msg = "Can't create a hardware ethernet device."
        raise DeviceError(msg)

    def destroy(self):
        """Destroys the netdevice of the corresponding type

        For the basic eth device it just cleans up its configuration.
        """
        self.cleanup()
        return True

    def cleanup(self):
        """Cleans up the device configuration

        Flushes the entire device configuration as appropriate for the given
        device. That includes setting the device 'down', flushing IP addresses
        and resetting device properties (MTU, name, etc.) to their original
        values.
        """
        if self.master:
            self.master = None
        self.down()
        self.ip_flush()
        self._clear_tc_qdisc()
        self._clear_tc_filters()
        self._restore_original_data()

    @property
    def link_header_type(self):
        """link_header_type attribute

        Returns the integer type of the link layer header as reported by the
        kernel. See ARPHRD constants in /usr/include/linux/if_arp.h.
        """
        return self._nl_msg['ifi_type']

    @property
    def name(self):
        """name attribute

        Returns string name of the device as reported by the kernel.
        """
        return self._nl_msg.get_attr("IFLA_IFNAME")

    @name.setter
    def name(self, new_name):
        """set name of the interface

        Args:
            new_name -- the new name of the interface.
        """
        self._update_attr(new_name, "IFLA_IFNAME")
        self._nl_sync("set")

    @property
    def hwaddr(self):
        """hwaddr attribute getter

        Returns a HWAddress object representing the hardware address of the
        device as reported by the kernel.
        """
        return hwaddress(self._nl_msg.get_attr("IFLA_ADDRESS"))

    @hwaddr.setter
    def hwaddr(self, addr):
        """hwaddr attribute setter

        Args:
            addr -- an address accepted by the hwaddress factory method
        """
        addr = hwaddress(addr)
        self._update_attr(str(addr), "IFLA_ADDRESS")
        self._nl_sync("set")

    @property
    def state(self):
        """state attribute

        Returns list of strings representing the current state of the device
        as reported by the kernel.
        """
        flags = self._nl_msg["flags"]
        return [ifinfmsg.IFF_VALUES[i][4:].lower() for i in ifinfmsg.IFF_VALUES if flags & i]
        #TODO add passive wait until lower up, with timeout

    @property
    def ips(self):
        """list of configured ip addresses

        Returns list of BaseIpAddress objects.
        """
        return self._ip_addrs

    @property
    def mtu(self):
        """mtu attribute

        Returns integer MTU as reported by the kernel.
        """
        return self._nl_msg.get_attr("IFLA_MTU")

    @mtu.setter
    def mtu(self, value):
        """set MTU of the interface

        Args:
            value -- the new MTU."""
        self._update_attr(int(value), "IFLA_MTU")
        self._nl_sync("set")

    @property
    def master(self):
        """master device

        Returns Device object of the master device or None when the device has
        no master.
        """
        master_ifindex = self._nl_msg.get_attr("IFLA_MASTER")
        if master_ifindex is not None:
            return self._if_manager.get_device(master_ifindex)
        else:
            return None

    @master.setter
    def master(self, dev):
        """set dev as the master of this device

        Args:
            dev -- accepts a Device object of the master object.
                When None, removes the current master from the Device."""
        if isinstance(dev, Device):
            master_idx = dev.ifindex
        elif dev is None:
            master_idx = 0
        else:
            raise DeviceError("Invalid dev argument.")

        self._update_attr(master_idx, "IFLA_MASTER")
        self._nl_sync("set")

    @property
    def driver(self):
        """driver attribute

        Returns string name of the device driver as reported by the kernel.
        Tries several methods to obtain the name.
        """
        if self.link_header_type == 772:  # loopback header type
            return 'loopback'
        linkinfo = self._nl_msg.get_attr("IFLA_LINKINFO")
        if linkinfo:
            result = linkinfo.get_attr("IFLA_INFO_KIND")
            if result and result != "unknown":
                # pyroute2 tries to be too clever and second guesses the
                # driver; when it fails, it fills in "unknown". We need to
                # ignore it.
                return result
        try:
            return ethtool.get_module(self.name)
        except IOError:
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

    def _ip_add_one(self, addr):
        ip = ipaddress(addr)
        if ip not in self.ips:
            with pyroute2.IPRoute() as ipr:
                try:
                    ipr.addr("add", index=self.ifindex, address=str(ip),
                             mask=ip.prefixlen)
                    self._if_manager.handle_netlink_msgs()
                except pyroute2.netlink.NetlinkError:
                    log_exc_traceback()
                    raise DeviceConfigValueError("Invalid IP address")

    def ip_add(self, addr):
        """add an ip address or a list of ip addresses

        Args:
            addr -- an address accepted by the ipaddress factory method
                    or a list of addresses accepted by the ipaddress
                    factory method
        """

        if isinstance(addr, list):
            for oneaddr in addr:
                self._ip_add_one(oneaddr)
        else:
            self._ip_add_one(addr)

    def _ip_del_one(self, addr):
        ip = ipaddress(addr)
        if ip in self.ips:
            with pyroute2.IPRoute() as ipr:
                try:
                    ipr.addr("del", index=self.ifindex, address=str(ip),
                             mask=ip.prefixlen)
                    self._if_manager.handle_netlink_msgs()
                except pyroute2.netlink.NetlinkError:
                    log_exc_traceback()
                    raise DeviceConfigValueError("Invalid IP address")

    def ip_del(self, addr):
        """remove an ip address or a list of ip addresses

        Args:
            addr -- an address accepted by the ipaddress factory method
                    or a list of addresses accepted by the ipaddress
                    factory method
        """
        if isinstance(addr, list):
            for oneaddr in addr:
                self._ip_del_one(oneaddr)
        else:
            self._ip_del_one(addr)

    def ip_flush(self):
        """flush all ip addresses of the device"""
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.flush_addr(index=self.ifindex)
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("IP address flush failed")

    def up(self):
        """set device up"""
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.link("set", index=self.ifindex, state="up")
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Setting link up failed.")

    def down(self):
        """set device down"""
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.link("set", index=self.ifindex, state="down")
                self._if_manager.handle_netlink_msgs()
            except pyroute2.netlink.NetlinkError:
                log_exc_traceback()
                raise DeviceConfigError("Setting link down failed.")

    #TODO looks like python ethtool module doesn't support these so we'll keep
    #exec_cmd for now...
    def speed_set(self, speed):
        """set the device speed

        Also disables automatic speed negotiation

        Args:
            speed -- string accepted by the 'ethtool -s dev speed ' command
        """
        try:
            int(speed)
        except:
            raise DeviceConfigValueError("Invalid link speed value %s" %
                                         str(speed))
        exec_cmd("ethtool -s %s speed %d" % (self.name, speed))

    def autoneg_on(self):
        """enable automatic negotiation of speed for this device"""
        exec_cmd("ethtool -s %s autoneg on" % self.name)

    def autoneg_off(self):
        """disable automatic negotiation of speed for this device"""
        exec_cmd("ethtool -s %s autoneg off" % self.name)

    #TODO implement proper Route objects
    #consider the same as with tc?
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
