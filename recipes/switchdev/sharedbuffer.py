"""
Copyright 2016 Mellanox Technologies. All rights reserved.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jiri@mellanox.com (Jiri Pirko)
"""

from lnst.Controller.Task import ctl
from TestLib import TestLib
from time import sleep
import random

class RandomValuePicker:
    def __init__(self, pools):
        self._pools = {"ingress": [], "egress": []}
        for pool in pools:
            self._pools[pool["type"]].append(pool["pool"])

    def _get_size(self):
        # support only this fixed size for now
        return 12401088

    def _get_thtype(self):
        # support static threshold only for now
        return "static"

    def _get_th(self):
        # support dynamic threshold only for now
        return random.randint(3,16)

    def _get_pool(self, direction):
        arr = self._pools[direction]
        return arr[random.randint(0, len(arr) - 1)]

    def get_value(self, objid):
        if isinstance(objid, Pool):
            return (self._get_size(), self._get_thtype())
        if isinstance(objid, TcBind):
            pool = self._get_pool(objid["type"])
            th = self._get_th()
            return (pool, th)
        if isinstance(objid, PortPool):
            return (self._get_th(),)

class RecordValuePickerException(Exception):
    pass

class RecordValuePicker:
    def __init__(self, objlist):
        self._recs = []
        for item in objlist:
            self._recs.append({"objid": item, "value": item.var_tuple()})

    def get_value(self, objid):
        for rec in self._recs:
            if rec["objid"].weak_eq(objid):
                return rec["value"]
        raise RecordValuePickerException()

class RunCmdException(Exception):
    pass

def run_cmd(host, cmd, json=False):
    cmd = host.run(cmd, json=json)
    if not cmd.passed():
        raise RunCmdException(cmd.get_result()["res_data"]["stderr"])
    return cmd.out()

def run_json_cmd(host, cmd):
    return run_cmd(host, cmd, json=True)

class CommonItem(dict):
    varitems = []

    def var_tuple(self):
        ret = []
        self.varitems.sort()
        for key in self.varitems:
            ret.append(self[key])
        return tuple(ret)

    def weak_eq(self, other):
        for key in self:
            if key in self.varitems:
                continue
            if self[key] != other[key]:
                return False
        return True

class CommonList(list):
    def get_by(self, by_obj):
        for item in self:
            if item.weak_eq(by_obj):
                return item
        return None

    def del_by(self, by_obj):
        for item in self:
            if item.weak_eq(by_obj):
                self.remove(item)

class Pool(CommonItem):
    varitems = ["size", "thtype"]

    def dl_set(self, sw, dlname, size, thtype):
        run_cmd(sw, "devlink sb pool set {} sb {} pool {} size {} thtype {}".format(dlname, self["sb"],
                                                                                    self["pool"],
                                                                                    size, thtype))

class PoolList(CommonList):
    pass

def get_pools(sw, dlname, direction=None):
    d = run_json_cmd(sw, "devlink sb pool show -j")
    pools = PoolList()
    for pooldict in d["pool"][dlname]:
        if not direction or direction == pooldict["type"]:
            pools.append(Pool(pooldict))
    return pools

def do_check_pools(tl, sw, dlname, pools, vp):
    for pool in pools:
        pre_pools = get_pools(sw, dlname)
        (size, thtype) = vp.get_value(pool)
        pool.dl_set(sw, dlname, size, thtype)
        post_pools = get_pools(sw, dlname)
        pool = post_pools.get_by(pool)

        err_msg = None
        if pool["size"] != size:
            err_msg = "Incorrect pool size (got {}, expected {})".format(pool["size"], size)
        if pool["thtype"] != thtype:
            err_msg = "Incorrect pool threshold type (got {}, expected {})".format(pool["thtype"], thtype)

        pre_pools.del_by(pool)
        post_pools.del_by(pool)
        if pre_pools != post_pools:
            err_msg = "Other pool setup changed as well"
        tl.custom(sw, "pool {} of sb {} set verification".format(pool["pool"],
                                                                 pool["sb"]), err_msg)

def check_pools(tl, sw, dlname, pools):
    record_vp = RecordValuePicker(pools)
    do_check_pools(tl, sw, dlname, pools, RandomValuePicker(pools))
    do_check_pools(tl, sw, dlname, pools, record_vp)

class TcBind(CommonItem):
    varitems = ["pool", "threshold"]

    def __init__(self, port, d):
        super(TcBind, self).__init__(d)
        self["dlportname"] = port.name

    def dl_set(self, sw, pool, th):
        run_cmd(sw, "devlink sb tc bind set {} sb {} tc {} type {} pool {} th {}".format(self["dlportname"],
                                                                                         self["sb"],
                                                                                         self["tc"],
                                                                                         self["type"],
                                                                                         pool, th))

class TcBindList(CommonList):
    pass

def get_tcbinds(tl, sw, ports, verify_existence=False):
    d = run_json_cmd(sw, "devlink sb tc bind show -j -n")
    tcbinds = TcBindList()
    for port in ports:
        err_msg = None
        if not port.name in d["tc_bind"] or len(d["tc_bind"][port.name]) == 0:
            err_msg = "No tc bind for port"
        else:
            for tcbinddict in d["tc_bind"][port.name]:
                tcbinds.append(TcBind(port, tcbinddict))
        if verify_existence:
            tl.custom(sw, "tc bind existence for port {} verification".format(port.name, err_msg))
    return tcbinds

def do_check_tcbind(tl, sw, ports, tcbinds, vp):
    for tcbind in tcbinds:
        pre_tcbinds = get_tcbinds(tl, sw, ports)
        (pool, th) = vp.get_value(tcbind)
        tcbind.dl_set(sw, pool, th)
        post_tcbinds = get_tcbinds(tl, sw, ports)
        tcbind = post_tcbinds.get_by(tcbind)

        err_msg = None
        if tcbind["pool"] != pool:
            err_msg = "Incorrect pool (got {}, expected {})".format(tcbind["pool"], pool)
        if tcbind["threshold"] != th:
            err_msg = "Incorrect threshold (got {}, expected {})".format(tcbind["threshold"], th)

        pre_tcbinds.del_by(tcbind)
        post_tcbinds.del_by(tcbind)
        if pre_tcbinds != post_tcbinds:
            err_msg = "Other tc bind setup changed as well"
        tl.custom(sw, "tc bind {}-{} of sb {} set verification".format(tcbind["dlportname"],
                                                                       tcbind["tc"],
                                                                       tcbind["sb"]), err_msg)

def check_tcbind(tl, sw, dlname, ports, pools):
    tcbinds = get_tcbinds(tl, sw, ports, verify_existence=True)
    record_vp = RecordValuePicker(tcbinds)
    do_check_tcbind(tl, sw, ports, tcbinds, RandomValuePicker(pools))
    do_check_tcbind(tl, sw, ports, tcbinds, record_vp)

class PortPool(CommonItem):
    varitems = ["threshold"]

    def __init__(self, port, d):
        super(PortPool, self).__init__(d)
        self["dlportname"] = port.name

    def dl_set(self, sw, th):
        run_cmd(sw, "devlink sb port pool set {} sb {} pool {} th {}".format(self["dlportname"],
                                                                             self["sb"],
                                                                             self["pool"], th))

class PortPoolList(CommonList):
    pass

def get_portpools(tl, sw, ports, verify_existence=False):
    d = run_json_cmd(sw, "devlink sb port pool -j -n")
    portpools = PortPoolList()
    for port in ports:
        err_msg = None
        if not port.name in d["port_pool"] or len(d["port_pool"][port.name]) == 0:
            err_msg = "No port pool for port"
        else:
            for portpooldict in d["port_pool"][port.name]:
                portpools.append(PortPool(port, portpooldict))
        if verify_existence:
            tl.custom(sw, "port pool existence for port {} verification".format(port.name, err_msg))
    return portpools

def do_check_portpool(tl, sw, ports, portpools, vp):
    for portpool in portpools:
        pre_portpools = get_portpools(tl, sw, ports)
        (th,) = vp.get_value(portpool)
        portpool.dl_set(sw, th)
        post_portpools = get_portpools(tl, sw, ports)
        portpool = post_portpools.get_by(portpool)

        err_msg = None
        if portpool["threshold"] != th:
            err_msg = "Incorrect threshold (got {}, expected {})".format(portpool["threshold"], th)

        pre_portpools.del_by(portpool)
        post_portpools.del_by(portpool)
        if pre_portpools != post_portpools:
            err_msg = "Other port pool setup changed as well"
        tl.custom(sw, "port pool {}-{} of sb {} set verification".format(portpool["dlportname"],
                                                                         portpool["pool"],
                                                                         portpool["sb"]), err_msg)

def check_portpool(tl, sw, dlname, ports, pools):
    portpools = get_portpools(tl, sw, ports, verify_existence=True)
    record_vp = RecordValuePicker(portpools)
    do_check_portpool(tl, sw, ports, portpools, RandomValuePicker(pools))
    do_check_portpool(tl, sw, ports, portpools, record_vp)

class Port:
    def __init__(self, name):
        self.name = name

class PortList(list):
    pass

def get_ports(sw, dlname):
    d = run_json_cmd(sw, "devlink port show -j")
    ports = PortList()
    for name in d["port"]:
        if name.find(dlname) == 0:
            ports.append(Port(name))
    return ports

class UnavailableDevlinkNameException(Exception):
    pass

def do_task(ctl, hosts, ifaces, aliases):
    m1, m2, sw = hosts
    m1_if1, m2_if1, sw_if1, sw_if2 = ifaces

    tl = TestLib(ctl, aliases)

    dlname = sw_if1.get_devlink_name()
    if not dlname:
        raise UnavailableDevlinkNameException()

    ports = get_ports(sw, dlname)
    pools = get_pools(sw, dlname)
    check_pools(tl, sw, dlname, pools)
    check_tcbind(tl, sw, dlname, ports, pools)
    check_portpool(tl, sw, dlname, ports, pools)

do_task(ctl, [ctl.get_host("machine1"),
              ctl.get_host("machine2"),
              ctl.get_host("switch")],
        [ctl.get_host("machine1").get_interface("if1"),
         ctl.get_host("machine2").get_interface("if1"),
         ctl.get_host("switch").get_interface("if1"),
         ctl.get_host("switch").get_interface("if2")],
        ctl.get_aliases())
