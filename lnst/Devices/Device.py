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
import time
from abc import ABCMeta
from itertools import product
from pyroute2.netlink.rtnl import ifinfmsg
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.DeviceError import DeviceError, DeviceDeleted, DeviceDisabled
from lnst.Common.DeviceError import DeviceConfigError, DeviceConfigValueError
from lnst.Common.DeviceError import DeviceFeatureNotSupported
from lnst.Common.IpAddress import ipaddress, AF_INET
from lnst.Common.HWAddress import hwaddress
from lnst.Common.Utils import wait_for_condition

from pyroute2.netlink.rtnl import RTM_NEWLINK
from pyroute2.netlink.rtnl import RTM_NEWADDR
from pyroute2.netlink.rtnl import RTM_DELADDR

TOGGLE_STATE_TIMEOUT = 15 + 3  # as a reserve

class DeviceMeta(ABCMeta):
    def __instancecheck__(self, other):
        try:
            return issubclass(other._dev_cls, self)
        except AttributeError:
            return super(DeviceMeta, self).__instancecheck__(other)

def sriov_capable(func):
    """
    Decorator for Device class methods that checks whether the Device is
    capable of SR-IOV.
    """
    def wrapper(self, *args, **kwargs):
        try:
            exec_cmd(f"cat /sys/class/net/{self.name}/device/sriov_numvfs")
        except ExecCmdFail:
            raise DeviceFeatureNotSupported(f"Device {self.name} not SR-IOV capable")

        return func(self, *args, **kwargs)

    return wrapper

def switchdev_capable(func):
    """
    Decorator for Device class methods that checks whether the Device can be
    used in switchdev mode.
    """
    def wrapper(self, *args, **kwargs):
        try:
            _ = self.eswitch_mode
        except DeviceFeatureNotSupported:
            raise

        return func(self, *args, **kwargs)

    return wrapper

class Device(object, metaclass=DeviceMeta):
    """The base Device class

    Implemented using the pyroute2 package to access different attributes of
    a kernel netdevice object.
    Changing attributes of a netdevice is right now implemented by calling
    shell commands (e.g. from iproute2 package).

    The Controller-Agent communication is implemented in such a way that all
    public methods defined in this and derived class are directly available
    as a tester facing API.
    """

    def __init__(self, if_manager):
        self.ifindex = None
        self._nl_msg = None
        self._devlink = None
        self._if_manager = if_manager
        self._enabled = True
        self._deleted = False

        self._ip_addrs = []

        self._nl_link_update = {}
        self._bulk_enabled = False

        self._cleanup_data = None

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
        self._set_nested_nl_attr(self._nl_link_update, value, *args)

    def _process_nested_nl_attrs(self, msg):
        ret = {}
        for k, v in msg.items():
            if isinstance(v, dict):
                processed = self._process_nested_nl_attrs(v["attrs"])
                ret[k] = {"attrs": list(processed.items())}
            else:
                ret[k] = v
        return ret

    def _nl_link_sync(self, op, ipr_attrs=None, bulk=False):
        if self._bulk_enabled and not bulk:
            return

        if ipr_attrs is None:
            attrs = self._process_nested_nl_attrs(self._nl_link_update)
        else:
            attrs = self._process_nested_nl_attrs(ipr_attrs)

        if op == "add":
            self._ipr_wrapper("link", op, **attrs)
        else:
            self._ipr_wrapper("link", op, index=self.ifindex, **attrs)

        if ipr_attrs is None:
            self._nl_link_update = {}

    def _ipr_wrapper(self, obj_name, op_name, *args, **kwargs):
        pretty_attrs = pprint.pformat({"args": args, "kwargs": kwargs})
        logging.debug("Performing pyroute.IPRoute().{}({}, *args, **kwargs)".format(obj_name, op_name))
        logging.debug("{}".format(pretty_attrs))

        ret_val = None
        with pyroute2.IPRoute() as ipr:
            try:
                obj = getattr(ipr, obj_name)
                if op_name is not None:
                    ret_val = obj(op_name, *args, **kwargs)
                else:
                    ret_val = obj(*args, **kwargs)
                self._if_manager.rescan_devices()
            except Exception as e:
                log_exc_traceback()
                raise DeviceConfigError("Object {} operation {} on link {} failed: {}"
                        .format(obj_name, op_name, self.name, str(e)))
        return ret_val

    def _enable(self):
        """Enables the Device object"""
        self._enabled = True

    def _disable(self):
        """Disables the Device object

        When a Device object is disabled, any calls to it's methods will result
        in a "no operation", however attribute access will still work.

        The justification for this is to disable the Device used by the
        Controller-Agent connection to avoid accidental disconnects.
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

    def _update_netlink(self, nl_msg):
        if getattr(self, "_deleted"):
            raise DeviceDeleted("Device was deleted.")

        if self.ifindex != nl_msg['index']:
            msg = "ifindex of netlink message (%s) doesn't match "\
                  "the device's (%s)." % (nl_msg['index'], self.ifindex)
            raise DeviceError(msg)

        if nl_msg['header']['type'] == RTM_NEWLINK:
            self._nl_msg = nl_msg
        elif nl_msg['header']['type'] == RTM_NEWADDR:
            if nl_msg['family'] == AF_INET:
                """
                from if_addr.h:
                /*
                 * Important comment:
                 * IFA_ADDRESS is prefix address, rather than local interface address.
                 * It makes no difference for normally configured broadcast interfaces,
                 * but for point-to-point IFA_ADDRESS is DESTINATION address,
                 * local address is supplied in IFA_LOCAL attribute.
                 */
                """
                addr = ipaddress(nl_msg.get_attr('IFA_LOCAL'),
                                 flags=nl_msg.get_attr("IFA_FLAGS"))
            else:
                addr = ipaddress(nl_msg.get_attr('IFA_ADDRESS'),
                                 flags=nl_msg.get_attr("IFA_FLAGS"))

            addr.prefixlen = nl_msg["prefixlen"]

            if addr not in self._ip_addrs:
                self._ip_addrs.append(addr)
            else:
                old_idx = self._ip_addrs.index(addr)
                addr_old = self._ip_addrs[old_idx]
                if addr.flags != addr_old.flags:
                    self._ip_addrs.pop(old_idx)
                    self._ip_addrs.append(addr)

        elif nl_msg['header']['type'] == RTM_DELADDR:
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
        try:
            ad_rx_coal, ad_tx_coal = self._read_adaptive_coalescing()
        except DeviceError:
            ad_rx_coal, ad_tx_coal = None, None
        if_data["adaptive_rx_coalescing"] = ad_rx_coal
        if_data["adaptive_tx_coalescing"] = ad_tx_coal

        try:
            rx_pause, tx_pause = self._read_pause_frames()
        except DeviceError:
            rx_pause, tx_pause = None, None
        if_data["rx_pause"] = rx_pause
        if_data["tx_pause"] = tx_pause

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

    def store_cleanup_data(self):
        """Stores initial configuration for later cleanup"""
        if self._cleanup_data:
            logging.debug("Previous cleanup data present, possible deconfigration failure in the past?")

        self._cleanup_data = {
                "mtu": self.mtu,
                "name": self.name,
                "hwaddr": self.hwaddr}
        try:
            ad_rx_coal, ad_tx_coal = self._read_adaptive_coalescing()
        except DeviceError:
            ad_rx_coal, ad_tx_coal = None, None
        self._cleanup_data["adaptive_rx_coalescing"] = ad_rx_coal
        self._cleanup_data["adaptive_tx_coalescing"] = ad_tx_coal

        try:
            rx_pause, tx_pause = self._read_pause_frames()
        except DeviceError:
            rx_pause, tx_pause = None, None
        self._cleanup_data.update(
                {
                    "rx_pause": rx_pause,
                    "tx_pause": tx_pause
                })

        self._cleanup_data["coalescing_settings"] = self._read_coalescing_settings()

    def restore_original_data(self):
        """Restores initial configuration from stored values"""
        if not self._cleanup_data:
            logging.debug("No cleanup data present")
            return

        if self.mtu != self._cleanup_data["mtu"]:
            self.mtu = self._cleanup_data["mtu"]

        if self.name != self._cleanup_data["name"]:
            self.name = self._cleanup_data["name"]

        if self.hwaddr != self._cleanup_data["hwaddr"]:
            self.hwaddr = self._cleanup_data["hwaddr"]

        try:
            self.restore_coalescing()
        except DeviceError as e:
            logging.warn(e)

        # the device needs to be up to configure the pause frame settings
        self.up()
        self.restore_pause_frames()
        self.down()

        self._cleanup_data = None

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
            self.master.cleanup()
            self.master = None

        try:
            if self.state != "up":
                self.up_and_wait()

            self.delete_vfs()
        except DeviceFeatureNotSupported:
            pass

        self.down()
        self.ip_flush()
        self._clear_tc_qdisc()
        self._clear_tc_filters()

        self.restore_original_data()

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
        self._nl_link_sync("set")

    @property
    def hwaddr(self):
        """hwaddr attribute getter

        Returns a HWAddress object representing the hardware address of the
        device as reported by the kernel.
        """
        if self._nl_msg.get_attr("IFLA_ADDRESS"):
            return hwaddress(self._nl_msg.get_attr("IFLA_ADDRESS"))
        else:
            return None

    @hwaddr.setter
    def hwaddr(self, addr):
        """hwaddr attribute setter

        Args:
            addr -- an address accepted by the hwaddress factory method
        """
        addr = hwaddress(addr)
        self._update_attr(str(addr), "IFLA_ADDRESS")
        self._nl_link_sync("set")

    @property
    def adaptive_rx_coalescing(self):
        try:
            res = self._read_adaptive_coalescing()
        except DeviceFeatureNotSupported:
            return False
        return res[0] == 'on'

    @adaptive_rx_coalescing.setter
    def adaptive_rx_coalescing(self, value):
        rx_val = 'off'
        if value:
            rx_val = 'on'
        tx_val = self._read_adaptive_coalescing()[1]
        self._write_adaptive_coalescing(rx_val, tx_val)

    @property
    def adaptive_tx_coalescing(self):
        try:
            res = self._read_adaptive_coalescing()
        except DeviceFeatureNotSupported:
            return False
        return res[1] == 'on'


    @adaptive_tx_coalescing.setter
    def adaptive_tx_coalescing(self, value):
        tx_val = 'off'
        if value:
            tx_val = 'on'
        rx_val = self._read_adaptive_coalescing()[0]
        self._write_adaptive_coalescing(rx_val, tx_val)

    @property
    def coalescing_rx_usecs(self):
        try:
            return self._read_coalescing_settings()["rx-usecs"]
        except KeyError:
            return None

    @coalescing_rx_usecs.setter
    def coalescing_rx_usecs(self, value):
        self._write_coalescing_setting("rx-usecs", value)

    @property
    def coalescing_tx_usecs(self):
        try:
            return self._read_coalescing_settings()["tx-usecs"]
        except KeyError:
            return None

    @coalescing_tx_usecs.setter
    def coalescing_tx_usecs(self, value):
        self._write_coalescing_setting("tx-usecs", value)

    @property
    def coalescing_rx_frames(self):
        try:
            return self._read_coalescing_settings()["rx-frames"]
        except KeyError:
            return None

    @coalescing_rx_frames.setter
    def coalescing_rx_frames(self, value):
        self._write_coalescing_setting("rx-frames", value)

    @property
    def coalescing_tx_frames(self):
        try:
            return self._read_coalescing_settings()["tx-frames"]
        except KeyError:
            return None

    @coalescing_tx_frames.setter
    def coalescing_tx_frames(self, value):
        self._write_coalescing_setting("tx-frames", value)

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
        self._nl_link_sync("set")

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
        self._nl_link_sync("set")

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

    @property
    def bus_info(self):
        try:
            return ethtool.get_businfo(self.name)
        except IOError as e:
            raise DeviceFeatureNotSupported(f"No bus info for {self.name}")

    def ip_add(self, addr, peer=None):
        """add an ip address

        Args:
            addr -- an address accepted by the ipaddress factory method
            peer -- an address of a peer interface for point-to-point
                    deployments, accepted by the ipaddress factory method
        """
        ip = ipaddress(addr)
        if ip not in self.ips:
            kwargs = dict(
                index=self.ifindex,
                local=str(ip),
                address=str(ip),
                mask=ip.prefixlen
            )
            if peer:
                kwargs['address'] = str(ipaddress(peer))

            self._ipr_wrapper("addr", "add", **kwargs)

        for i in range(5):
            logging.debug("Waiting for ip address to be added {} of 5".format(i))
            time.sleep(1)
            self._if_manager.rescan_devices()
            if addr in self.ips:
                break
        else:
            raise DeviceError("Failed to configure ip address {}".format(str(ip)))

    def ip_del(self, addr):
        """remove an ip address

        Args:
            addr -- an address accepted by the ipaddress factory method
        """
        ip = ipaddress(addr)
        if ip in self.ips:
            self._ipr_wrapper("addr", "del", index=self.ifindex,
                              address=str(ip), mask=ip.prefixlen)

    def ip_flush(self, scope=0):
        """flush all ip addresses of the device"""
        self._ipr_wrapper("flush_addr", None, index=self.ifindex, scope=scope)

    def ips_filter(self, **selectors):
        result = []
        for addr in self.ips:
            match = True
            for selector, value in selectors.items():
                try:
                    if getattr(addr, selector) != value:
                        match = False
                        break
                except:
                    match = False
            if match:
                result.append(addr)
        return result

    def up(self):
        """set device up"""
        self._nl_link_update["state"] = "up"
        self._nl_link_sync("set")

    def down(self):
        """set device down"""
        self._nl_link_update["state"] = "down"
        self._nl_link_sync("set")

    def up_and_wait(self, timeout: int = TOGGLE_STATE_TIMEOUT):
        self.up()
        wait_for_condition(lambda: "up" in self.state, timeout=timeout)

    def down_and_wait(self, timeout: int = TOGGLE_STATE_TIMEOUT):
        self.down()
        wait_for_condition(lambda: "up" not in self.state, timeout=timeout)

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

    def _read_adaptive_coalescing(self):
        res, _ = exec_cmd("ethtool -c %s" % self.name, die_on_err=False)

        regex = "Adaptive RX: (on|off)  TX: (on|off)"
        try:
            res = re.search(regex, res).groups()
        except AttributeError:
            raise DeviceFeatureNotSupported(
                "No values for coalescence of %s." % self.name
            )
        return list(res)

    def _write_adaptive_coalescing(self, rx_val, tx_val):
        if self._read_adaptive_coalescing() == [rx_val, tx_val]:
            return
        try:
            exec_cmd("ethtool -C %s adaptive-rx %s adaptive-tx %s" %
                     (self.name, rx_val, tx_val))
        except:
            raise DeviceFeatureNotSupported(
                "Not allowed to modify coalescence settings for %s." % self.name
            )

    def restore_coalescing(self):
        for setting, value in self._cleanup_data["coalescing_settings"].items():
            if value != 'n/a':
                self._write_coalescing_setting(setting, value)

        rx_val = self._cleanup_data["adaptive_rx_coalescing"]
        tx_val = self._cleanup_data["adaptive_tx_coalescing"]
        if (rx_val, tx_val) != (None, None):
            self._write_adaptive_coalescing(rx_val, tx_val)

    def _read_coalescing_settings(self):
        settings = {}
        output, _ = exec_cmd("ethtool -c %s" % self.name, die_on_err=False)

        regex = re.compile("^([a-z-]+):\s+(n/a|\d+)$")

        for line in output.split('\n'):
            if not (m := regex.match(line)):
                continue
            setting = m.group(1)
            value = m.group(2)
            settings[setting] = value

        return settings

    def _write_coalescing_setting(self, setting, value):
        try:
            exec_cmd(f"ethtool -C {self.name} {setting} {value}")
        except:
            raise DeviceFeatureNotSupported(
                f"Not allowed to modify coalescence settings {setting} for {self.name}."
            )

    @property
    def rx_pause_frames(self):
        try:
            res = self._read_pause_frames()
        except DeviceFeatureNotSupported:
            return None

        return res[0]

    @rx_pause_frames.setter
    def rx_pause_frames(self, value):
        self._write_pause_frames(value, None)

    @property
    def tx_pause_frames(self):
        try:
            res = self._read_pause_frames()
        except DeviceFeatureNotSupported:
            return None

        return res[1]

    @tx_pause_frames.setter
    def tx_pause_frames(self, value):
        self._write_pause_frames(None, value)

    def _read_pause_frames(self):
        try:
            res, _ = exec_cmd("ethtool -a %s" % self.name)
        except:
            raise DeviceFeatureNotSupported(
                "No values for pause frames of %s." % self.name
                )

        # TODO: add autonegotiate
        pause_settings = []
        regex = "(RX|TX):.*(on|off)"

        for line in res.split('\n'):
            m = re.search(regex, line)
            if m:
                setting = True if m.group(2) == 'on' else False
                pause_settings.append(setting)

        if len(pause_settings) != 2:
            raise Exception("Could not fetch pause frame settings. %s" % res)

        return pause_settings

    def _write_pause_frames(self, rx_val, tx_val):
        ethtool_cmd = "ethtool -A {}".format(self.name)
        ethtool_opts = ""

        for feature, value in [('rx', rx_val), ('tx', tx_val)]:
            if value is None:
                continue

            ethtool_opts += " {} {}".format(feature, 'on' if value else 'off')

        if len(ethtool_opts) == 0:
            return

        try:
            exec_cmd(ethtool_cmd + ethtool_opts)
        except ExecCmdFail as e:
            if e.get_retval() == 79:
                raise DeviceConfigError(
                    "Could not modify pause settings for %s." % self.name
                )

        timeout=5
        while timeout > 0:
            if self._pause_frames_match(rx_val, tx_val):
                break
            time.sleep(1)
            timeout -= 1

        if timeout == 0:
            raise DeviceError("Pause frames not set!")

    def _pause_frames_match(self, rx_expected, tx_expected):
        rx_value, tx_value = self._read_pause_frames()
        if ((rx_expected is not None and rx_expected != rx_value) or
                (tx_expected is not None and tx_expected != tx_value)):
            return False

        return True

    def restore_pause_frames(self):
        rx_val = self._cleanup_data["rx_pause"]
        tx_val = self._cleanup_data["tx_pause"]
        if (rx_val, tx_val) != (None, None):
            self._write_pause_frames(rx_val, tx_val)

    @property
    def eswitch_mode(self):
        try:
            # TODO: do this through device._devlink?
            stdout, _ = exec_cmd(f"devlink dev eswitch show pci/{self.bus_info}")
        except ExecCmdFail as e:
            if e.get_stderr().find("Operation not supported") > -1 or e.get_stderr().find("No such device"):
                raise DeviceFeatureNotSupported(f"Device {self.name} not compatible with switchdev")
            else:
                raise DeviceError(
                    f"Error while querying device {self.name} eswitch mode:\n{e.get_stderr()}"
                )

        m = re.search("mode (legacy|switchdev)", stdout)
        try:
            return m.group(1)
        except AttributeError:
            raise DeviceFeatureNotSupported(f"Could not parse device {self.name} eswitch mode")

    @eswitch_mode.setter
    def eswitch_mode(self, mode):
        if self.eswitch_mode == mode:
            return

        try:
            # TODO: do this through device._devlink?
            exec_cmd(f"devlink dev eswitch set pci/{self.bus_info} mode {mode}")
        except ExecCmdFail as e:
            raise DeviceError(
                f"Error while setting device {self.name} eswitch mode:\n{e.get_stderr()}"
            )

    @sriov_capable
    def create_vfs(self, number_of_vfs=1):
        try:
            exec_cmd(f"echo {number_of_vfs} > /sys/class/net/{self.name}/device/sriov_numvfs")
        except ExecCmdFail as e:
            raise DeviceError(
                f"Error while creating vfs for {self.name}:\n{e.get_stderr()}"
            )

        # wait for devices to appear on the netlink
        if not self._wait_for_vf_devices(number_of_vfs, 10):
            raise DeviceError(f"Error while waiting for vfs for {self.name}")

        for vf_dev in (vf_devices := self._get_vf_devices()):
            vf_dev._enable()

        try:
            eswitch_mode = self.eswitch_mode
        except DeviceFeatureNotSupported:
            return vf_devices, None

        if eswitch_mode == "switchdev":
            # wait for representor devices to appear on the netlink
            if not self._wait_for_vf_rep_devices(number_of_vfs, 10):
                raise DeviceError(f"Error while waiting for vf_reps for {self.name}")

            for vf_rep_dev in (vf_rep_devices := self._get_vf_rep_devices()):
                vf_rep_dev._enable()

            return vf_devices, vf_rep_devices

        # for any other cases, just return vf devices
        return vf_devices, None

    def _wait_for_vf_devices(self, vfs_count, timeout):
        if timeout > 0:
            logging.info(f"Waiting for vf(s) creation on PF {self.name} for {timeout} seconds")
        elif timeout == 0:
            logging.info(f"Waiting for vf(s) creation on PF {self.name}")

        def condition():
            return all(
                [
                    self._vf_is_ready(vf_index) for vf_index in range(0, vfs_count)
                ]
            )

        try:
            wait_for_condition(condition, timeout=timeout)
        except TimeoutError:
            logging.info(f"Timeout while waiting for vfs creation on PF {self.name}")
            raise

        logging.info(f"vfs on PF {self.name} successfully created")

        return True

    def _wait_for_vf_rep_devices(self, vfs_count, timeout):
        if timeout > 0:
            logging.info(f"Waiting for vf_rep(s) creation on PF {self.name} for {timeout} seconds")
        elif timeout == 0:
            logging.info(f"Waiting for vf_rep(s) creation on PF {self.name}")

        def condition():
            return all(
                [
                    self._vf_rep_is_ready(vf_index) for vf_index in range(0, vfs_count)
                ]
            )

        try:
            wait_for_condition(condition, timeout=timeout)
        except TimeoutError:
            logging.info(f"Timeout while waiting for vf_reps creation on PF {self.name}")
            raise

        logging.info(f"vf_reps on PF {self.name} successfully created")

        return True

    @sriov_capable
    def delete_vfs(self):
        try:
            exec_cmd(f"echo 0 > /sys/class/net/{self.name}/device/sriov_numvfs")
        except ExecCmdFail as e:
            raise DeviceError(
                f"Error while deleting vfs for {self.name}:\n{e.get_stderr()}"
            )

    def _vf_is_ready(self, vf_index):
        logging.debug(f"Waiting for {self.name} vf with index {vf_index}")
        # search for vf
        vf_device = self._get_vf(vf_index)

        if not vf_device:
            logging.debug(f"vf {vf_index} for {self.name} not ready")
            return False

        logging.debug(f"vf {vf_index} for {self.name} ready")

        return True

    def _vf_rep_is_ready(self, vf_index):
        logging.debug(f"Waiting for {self.name} vf_representor with index {vf_index}")

        # search for vf representor
        vf_rep_device = self._get_vf_representor(vf_index)

        if not vf_rep_device:
            logging.debug(f"vf representor {vf_index} for {self.name} not ready")
            return False

        logging.debug(f"vf representor {vf_index} for {self.name} ready")

        return True

    @sriov_capable
    def _get_vf_devices(self):
        return [
            self._get_vf(vf_index)
            for vf_index in range(self._get_vf_count())
        ]

    @switchdev_capable
    def _get_vf_rep_devices(self):
        return [
            self._get_vf_representor(vf_index)
            for vf_index in range(self._get_vf_count())
        ]

    def _get_vf_count(self):
        # TODO: create sysfs api for Device, then run self.[get|set]_sysfs("device/sriov_numvfs")
        stdout, _ = exec_cmd(f"cat /sys/class/net/{self.name}/device/sriov_numvfs")

        return int(stdout)

    def _get_vf_representor(self, vf_index: int):
        pf_number = int(self.phys_port_name[1:])

        vf_rep_device_phys_port_name = f"pf{pf_number}vf{vf_index}"
        all_devices = self._if_manager.get_devices()

        """
        netlink message content for vf representor devices
        1st message
        ('IFLA_PHYS_PORT_NAME', 'pf0vf0'),
        ('IFLA_PHYS_SWITCH_ID', '10:f7:d5:fe:ff:1a:3d:e4'),
        ('IFLA_PARENT_DEV_BUS_NAME', 'pci')
        ('IFLA_PARENT_DEV_NAME', '0000:01:00.0') is same as PF device

        2nd message, contains alternative device name derived from the PF device
        ('IFLA_PHYS_PORT_NAME', 'pf0vf0'),
        ('IFLA_PROP_LIST', {'attrs': [('IFLA_ALT_IFNAME', 'enp1s0f0npf0vf0')]}, 32768),
        ('IFLA_PARENT_DEV_NAME', '0000:01:00.0'),
        """
        vf_reps_match = [
            dev for dev in all_devices if (
                dev.phys_port_name == vf_rep_device_phys_port_name and
                dev.parent_dev_bus_name == self.parent_dev_bus_name and
                dev.parent_dev_name == self.parent_dev_name
            )
        ]

        try:
            return vf_reps_match[0]
        except IndexError:
            return None

    def _get_vf(self, vf_index: int):
        all_devices = self._if_manager.get_devices()

        """
        1st message
        ('IFLA_PARENT_DEV_BUS_NAME', 'pci')
        ('IFLA_PARENT_DEV_NAME', '0000:01:02.0'), is different from PF device

        2nd message, contains alternative device name derived from the PF device
        ('IFLA_PROP_LIST', {'attrs': [('IFLA_ALT_IFNAME', 'enp1s0f0v0')]}, 32768),
        """
        vfs_match = [
            dev for dev in all_devices if (
                dev != self and
                any(
                    [
                        pf_dev_name.find(vf_dev_name.rsplit(f"v{vf_index}")[0]) != -1
                        for vf_dev_name, pf_dev_name in product(dev.alt_if_names + [dev.name], self.alt_if_names + [self.name])
                    ]
                )
            )
        ]

        try:
            return vfs_match[0]
        except IndexError:
            return None

    @property
    def phys_port_name(self):
        return self._nl_msg.get("IFLA_PHYS_PORT_NAME")

    @property
    def parent_dev_bus_name(self):
        return self._nl_msg.get("IFLA_PARENT_DEV_BUS_NAME")

    @property
    def parent_dev_name(self):
        return self._nl_msg.get("IFLA_PARENT_DEV_NAME")

    @property
    def alt_if_names(self):
        try:
            return self._nl_msg.get_attr("IFLA_PROP_LIST").get_attrs("IFLA_ALT_IFNAME")
        except:
            return []

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
