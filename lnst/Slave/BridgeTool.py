"""
This module defines a class useful to work with "bridge" tool.

Copyright 2015 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.ExecCmd import exec_cmd
import re

class BridgeTool:
    def __init__(self, dev_name):
        self._dev_name = dev_name

    def _add_del_vlan(self, op, br_vlan_info):
        cmd = "bridge vlan %s dev %s vid %d" % (op, self._dev_name,
                                                br_vlan_info["vlan_id"])
        if br_vlan_info["pvid"]:
            cmd += " pvid"
        if br_vlan_info["untagged"]:
            cmd += " untagged"
        if br_vlan_info["self"]:
            cmd += " self"
        if br_vlan_info["master"]:
            cmd += " master"
        exec_cmd(cmd)

    def add_vlan(self, br_vlan_info):
        return self._add_del_vlan("add", br_vlan_info)

    def del_vlan(self, br_vlan_info):
        return self._add_del_vlan("del", br_vlan_info)

    def get_vlans(self):
        output = exec_cmd("bridge vlan show dev %s" % self._dev_name,
                          die_on_err=False)[0]
        br_vlan_info_list = []
        for line in output.split("\n"):
            match = re.match(r'.*\s+(\d+)', line)
            if match:
                vlan_id = int(match.groups()[0])
                pvid = True if re.match(r'.*\s+PVID', line) else False
                untagged = True if re.match(r'.*\s+Egress Untagged', line) \
                                else False
                br_vlan_info = {"vlan_id": vlan_id, "pvid": pvid,
                                "untagged": untagged}
                br_vlan_info_list.append(br_vlan_info)
        return br_vlan_info_list

    def _add_del_fdb(self, op, br_fdb_info):
        cmd = "bridge fdb %s %s dev %s" % (op, br_fdb_info["hwaddr"],
                                           self._dev_name)
        if br_fdb_info["self"]:
            cmd += " self"
        if br_fdb_info["master"]:
            cmd += " master"
        if br_fdb_info["vlan_id"]:
            cmd += " vlan %s" % br_fdb_info["vlan_id"]
        exec_cmd(cmd)

    def add_fdb(self, br_fdb_info):
        return self._add_del_fdb("add", br_fdb_info)

    def del_fdb(self, br_fdb_info):
        return self._add_del_fdb("del", br_fdb_info)

    def get_fdbs(_self):
        output = exec_cmd("bridge fdb show dev %s" % _self._dev_name,
                          die_on_err=False)[0]
        br_fdb_info_list = []
        for line in output.split("\n"):
            match = re.match(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', line)
            if match:
                hwaddr = normalize_hwaddr(match.groups()[0])
                match = re.match(r'.*\s+vlan (\d+)', line)
                vlan_id = int(match.groups()[0]) if match else 0
                self = True if re.match(r'.*\s+self', line) else False
                master = True if re.match(r'.*\s+master', line) else False
                offload = True if re.match(r'.*\s+offload', line) else False
                extern_learn = True if re.match(r'.*\s+extern_learn', line) else False
                br_fdb_info = {"hwaddr": hwaddr, "vlan_id": vlan_id,
                               "self": self, "master": master, "offload": offload,
                               "extern_learn": extern_learn}
                br_fdb_info_list.append(br_fdb_info)
        return br_fdb_info_list

    def _set_link(self, attr, br_link_info):
        cmd = "bridge link set dev %s %s" % (self._dev_name, attr)
        if br_link_info["on"]:
            cmd += " on"
        else:
            cmd += " off"
        if br_link_info["self"]:
            cmd += " self"
        if br_link_info["master"]:
            cmd += " master"
        exec_cmd(cmd)

    def set_learning(self, br_learning_info):
        return self._set_link("learning", br_learning_info)

    def set_learning_sync(self, br_learning_sync_info):
        return self._set_link("learning_sync", br_learning_sync_info)

    def set_flooding(self, br_flooding_info):
        return self._set_link("flood", br_flooding_info)

    def set_state(self, br_state_info):
        cmd = "bridge link set dev %s state %s" % (self._dev_name,
                                                   br_state_info["state"])
        if br_state_info["self"]:
            cmd += " self"
        if br_state_info["master"]:
            cmd += " master"
        exec_cmd(cmd)

    def set_mcast_snooping(self, set_on = True):
        cmd = "ip link set %s type bridge mcast_snooping %d" % (self._dev_name,
                                                                set_on)
        exec_cmd(cmd)

    def set_mcast_querier(self, set_on = True):
        cmd = "ip link set %s type bridge mcast_querier %d" % (self._dev_name,
                                                                set_on)
        exec_cmd(cmd)
