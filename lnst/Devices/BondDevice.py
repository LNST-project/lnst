"""
Defines the BondDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.HWAddress import hwaddress
from lnst.Common.IpAddress import ipaddress
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.Device import Device
from lnst.Devices.MasterDevice import MasterDevice

class BondDevice(MasterDevice):
    _name_template = "t_bond"
    _link_type = "bond"

    @property
    def active_slave(self):
        try:
            return self._get_linkinfo_data_attr("IFLA_BOND_ACTIVE_SLAVE")
        except:
            return None

    @active_slave.setter
    def active_slave(self, val):
        if not isinstance(val, Device):
            raise DeviceConfigError("Invalid value, must be Device.")

        self._set_linkinfo_data_attr("IFLA_BOND_ACTIVE_SLAVE", val.ifindex)
        self._nl_link_sync("set")

    @property
    def ad_actor_sys_prio(self):
        try:
            return int(
                    self._get_linkinfo_data_attr("IFLA_BOND_AD_ACTOR_SYS_PRIO"))
        except:
            return None

    @ad_actor_sys_prio.setter
    def ad_actor_sys_prio(self, val):
        if int(val) < 1 or int(val) > 65535:
            raise DeviceConfigError("Invalid value, must be 1-65535.")

        self._set_linkinfo_data_attr("IFLA_BOND_AD_ACTOR_SYS_PRIO", int(val))
        self._nl_link_sync("set")

    @property
    def ad_actor_system(self):
        try:
            return hwaddress(
                    self._get_linkinfo_data_attr("IFLA_BOND_AD_ACTOR_SYSTEM"))
        except:
            return None

    @ad_actor_system.setter
    def ad_actor_system(self, val):
        val = hwaddress(val)
        self._set_linkinfo_data_attr("IFLA_BOND_AD_ACTOR_SYSTEM", val)
        self._nl_link_sync("set")

    @property
    def ad_select(self):
        try:
            return self._get_linkinfo_data_attr("IFLA_BOND_AD_SELECT")
        except:
            return None

    @ad_select.setter
    def ad_select(self, val):
        m = dict(stable=0, bandwidth=1, count=2)
        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_AD_SELECT", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_AD_SELECT", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def ad_user_port_key(self):
        try:
            return self._get_linkinfo_data_attr("IFLA_BOND_AD_PORT_KEY")
        except:
            return None

    @ad_user_port_key.setter
    def ad_user_port_key(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_AD_PORT_KEY", int(val))
        self._nl_link_sync("set")

    @property
    def all_slaves_active(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_ALL_SLAVES_ACTIVE")

    @all_slaves_active.setter
    def all_slaves_active(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_ALL_SLAVES_ACTIVE", int(val))
        self._nl_link_sync("set")

    @property
    def arp_interval(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_ARP_INTERVAL")

    @arp_interval.setter
    def arp_interval(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_ARP_INTERVAL", int(val))
        self._nl_link_sync("set")

    @property
    def arp_ip_target(self):
        targets = self._get_linkinfo_data_attr("IFLA_BOND_ARP_IP_TARGET")
        if targets:
            targets = [ipaddress(x) for x in targets.split(',')]
        return targets

    @arp_ip_target.setter
    def arp_ip_target(self, val):
        if isinstance(val, list):
            new = []
            for i in val:
                try:
                    new.append(str(ipaddress(i)))
                except:
                    DeviceError("Invalid value, expected a list of ip addresses")
        elif val is None:
            new = []
        else:
            try:
                new = [ipaddress(val)]
            except:
                raise DeviceError("Invalid value, expected a list of ip addresses")

        ip_str = ",".join(new)
        self._set_linkinfo_data_attr("IFLA_BOND_ARP_IP_TARGET", ip_str)
        self._nl_link_sync("set")

    @property
    def arp_validate(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_ARP_VALIDATE")

    @arp_validate.setter
    def arp_validate(self, val):
        m = dict(none=0, active=1, backup=2, all=3, filter=4, filter_active=5,
                 filter_backup=6)

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_ARP_VALIDATE", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_ARP_VALIDATE", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def arp_all_targets(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_ARP_ALL_TARGETS")

    @arp_all_targets.setter
    def arp_all_targets(self, val):
        m = dict(any=0, all=1)

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_ARP_ALL_TARGETS", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_ARP_ALL_TARGETS", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def downdelay(self):
        return int(self._get_linkinfo_data_attr("IFLA_BOND_DOWNDELAY"))

    @downdelay.setter
    def downdelay(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_DOWNDELAY", int(val))
        self._nl_link_sync("set")

    @property
    def fail_over_mac(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_FAIL_OVER_MAC")

    @fail_over_mac.setter
    def fail_over_mac(self, val):
        m = dict(none=0, active=1, follow=2)

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_FAIL_OVER_MAC", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_FAIL_OVER_MAC", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def lacp_rate(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_LACP_RATE")

    @lacp_rate.setter
    def lacp_rate(self, val):
        m = dict(slow=0, fast=1)

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_LACP_RATE", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_LACP_RATE", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def miimon(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_MIIMON")

    @miimon.setter
    def miimon(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_LACP_RATE", int(val))
        self._nl_link_sync("set")

    @property
    def min_links(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_MIN_LINKS")

    @min_links.setter
    def min_links(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_MIN_LINKS", int(val))
        self._nl_link_sync("set")

    @property
    def mode(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_MODE")

    @mode.setter
    def mode(self, val):
        m = {"balance-rr": 0, "active-backup": 1, "balance-xor": 2,
             "broadcast": 3, "802.3ad": 4, "balance-tlb": 5, "balance-alb": 6}

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_MODE", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_MODE", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def num_peer_notif(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_NUM_PEER_NOTIF")

    @num_peer_notif.setter
    def num_peer_notif(self, val):
        if int(val) < 0 or int(val) > 255:
            raise DeviceConfigError("Invalid value, must be 0-255.")

        self._set_linkinfo_data_attr("IFLA_BOND_NUM_PEER_NOTIF", int(val))
        self._nl_link_sync("set")

    @property
    def packets_per_slave(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_PACKETS_PER_SLAVE")

    @packets_per_slave.setter
    def packets_per_slave(self, val):
        if int(val) < 0 or int(val) > 65535:
            raise DeviceConfigError("Invalid value, must be 0-65535.")

        self._set_linkinfo_data_attr("IFLA_BOND_PACKETS_PER_SLAVE", int(val))
        self._nl_link_sync("set")

    @property
    def primary(self):
        try:
            index = self._get_linkinfo_data_attr("IFLA_BOND_PRIMARY")
            return self._if_manager.get_device(index)
        except:
            return None

    @primary.setter
    def primary(self, val):
        if not isinstance(val, Device):
            raise DeviceConfigError("Invalid value, must be Device.")

        self._set_linkinfo_data_attr("IFLA_BOND_PRIMARY", val.ifindex)
        self._nl_link_sync("set")

    @property
    def primary_reselect(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_PRIMARY_RESELECT")

    @primary_reselect.setter
    def primary_reselect(self, val):
        m = {"always": 0, "better": 1, "failure": 2}

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_PRIMARY_RESELECT", m[val])
        elif val in m.values():
            self._set_linkinfo_data_attr("IFLA_BOND_PRIMARY_RESELECT", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {} or {}.".
                    format(list(m.keys()), list(m.values())))

        self._nl_link_sync("set")

    @property
    def tlb_dynamic_lb(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_TLB_DYNAMIC_LB")

    @tlb_dynamic_lb.setter
    def tlb_dynamic_lb(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_TLB_DYNAMIC_LB", bool(val))
        self._nl_link_sync("set")

    @property
    def updelay(self):
        return int(self._get_linkinfo_data_attr("IFLA_BOND_UPDELAY"))

    @updelay.setter
    def updelay(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_UPDELAY", int(val))
        self._nl_link_sync("set")

    @property
    def use_carrier(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_USE_CARRIER")

    @use_carrier.setter
    def use_carrier(self, val):
        self._set_linkinfo_data_attr("IFLA_BOND_USE_CARRIER", bool(val))
        self._nl_link_sync("set")

    @property
    def xmit_hash_policy(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_XMIT_HASH_POLICY")

    @xmit_hash_policy.setter
    def xmit_hash_policy(self, val):
        m = ["layer2", "layer2+3", "layer3+4", "encap2+3", "encap3+4"]

        if val in m:
            self._set_linkinfo_data_attr("IFLA_BOND_XMIT_HASH_POLICY", val)
        else:
            raise DeviceConfigError("Invalid value, must be in {}}.".format(m))
        self._nl_link_sync("set")

    @property
    def resend_igmp(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_RESEND_IGMP")

    @resend_igmp.setter
    def resend_igmp(self, val):
        if int(val) < 0 or int(val) > 255:
            raise DeviceConfigError("Invalid value, must be 0-255.")

        self._set_linkinfo_data_attr("IFLA_BOND_RESEND_IGMP", int(val))
        self._nl_link_sync("set")

    @property
    def lp_interval(self):
        return self._get_linkinfo_data_attr("IFLA_BOND_LP_INTERVAL")

    @lp_interval.setter
    def lp_interval(self, val):
        if int(val) < 1 or int(val) > 0x7fffffff:
            raise DeviceConfigError("Invalid value, must be 1-0x7fffffff.")

        self._set_linkinfo_data_attr("IFLA_BOND_LP_INTERVAL", int(val))
        self._nl_link_sync("set")
