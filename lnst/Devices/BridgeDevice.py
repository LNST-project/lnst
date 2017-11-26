"""
Defines the BridgeDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.ExecCmd import exec_cmd
from lnst.Devices.MasterDevice import MasterDevice

class BridgeDevice(MasterDevice):
    _name_template = "t_br"
    _link_type = "bridge"

    @property
    def ageing_time(self):
        return int(self._get_linkinfo_data_attr("IFLA_BR_AGEING_TIME"))

    @ageing_time.setter
    def ageing_time(self, val):
        self._set_linkinfo_data_attr("IFLA_BR_AGEING_TIME", int(val))
        self._nl_sync("set")

    @property
    def stp_state(self):
        return int(self._get_linkinfo_data_attr("IFLA_BR_STP_STATE"))

    @stp_state.setter
    def stp_state(self, val):
        self._set_linkinfo_data_attr("IFLA_BR_STP_STATE", int(val))
        self._nl_sync("set")

    @property
    def vlan_filtering(self):
        return bool(self._get_linkinfo_data_attr("IFLA_BR_VLAN_FILTERING"))

    @vlan_filtering.setter
    def vlan_filtering(self, val):
        self._set_linkinfo_data_attr("IFLA_BR_VLAN_FILTERING", bool(val))
        self._nl_sync("set")
