"""
This module contains implementaion of SlavePool class that
can be used to maintain a cluster of test machines.

These machines can be provisioned and used in test recipes.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import os
import re
import copy
from xml.dom import minidom
from lnst.Common.Config import lnst_config
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.NetUtils import test_tcp_connection
from lnst.Controller.XmlProcessing import XmlProcessingError, XmlData
from lnst.Controller.Machine import Machine
from lnst.Controller.SlaveMachineParser import SlaveMachineParser
from lnst.Controller.SlaveMachineParser import SlaveMachineError
from lnst.Common.Colours import decorate_with_preset
from lnst.Common.Utils import check_process_running

class SlavePool:
    """
    This class is responsible for managing test machines that
    are available at the controler and can be used for testing.
    """
    def __init__(self, pool_dirs, pool_checks=True):
        self._map = {}
        self._pool = {}

        self._machine_matches = []
        self._network_matches = []

        self._allow_virt = lnst_config.get_option("environment",
                                                  "allow_virtual")
        self._allow_virt &= check_process_running("libvirtd")
        self._pool_checks = pool_checks

        self._mapper = SetupMapper()
        self._mreqs = None

        logging.info("Checking machine pool availability.")
        for pool_dir in pool_dirs:
            self.add_dir(pool_dir)

        self._mapper.set_pool(self._pool)

    def add_dir(self, pool_dir):
        logging.info("Processing pool dir '%s'" % pool_dir)
        dentries = os.listdir(pool_dir)

        res = []
        for dirent in dentries:
            m_info = self.add_file("%s/%s" % (pool_dir, dirent))
            if m_info != None:
                res.append(m_info)

        if len(res) == 0:
            logging.warn("No machines found in this directory")

        max_len = 0
        for m_id, _ in res:
            if len(m_id) > max_len:
                max_len = len(m_id)
        for m_id, available in res:
            if available:
                machine_spec = self._pool[m_id]
                if 'libvirt_domain' in machine_spec['params']:
                    libvirt_msg = "   libvirt_domain: %s" %\
                                        machine_spec['params']['libvirt_domain']
                else:
                    libvirt_msg = ""
                msg = "%s%s [%s] %s" % (m_id, (max_len - len(m_id)) * " ",
                                        decorate_with_preset("UP", "pass"),
                                        libvirt_msg)
            else:
                msg = "%s%s [%s]" % (m_id, (max_len - len(m_id)) * " ",
                                     decorate_with_preset("DOWN", "fail"))

            logging.info(msg)

    def add_file(self, filepath):
        if os.path.isfile(filepath) and re.search("\.xml$", filepath, re.I):
            dirname, basename = os.path.split(filepath)
            m_id = re.sub("\.[xX][mM][lL]$", "", basename)

            parser = SlaveMachineParser(filepath)
            xml_data = parser.parse()
            machine_spec = self._process_machine_xml_data(m_id, xml_data)

            # Check if there isn't any machine with the same
            # hostname or libvirt_domain already in the pool
            for pm_id, m in self._pool.iteritems():
                pm = m["params"]
                rm = machine_spec["params"]
                if pm["hostname"] == rm["hostname"]:
                    msg = "You have the same machine listed twice in " \
                          "your pool ('%s' and '%s')." % (m_id, pm_id)
                    raise SlaveMachineError(msg)

                if "libvirt_domain" in rm and "libvirt_domain" in pm and \
                   pm["libvirt_domain"] == rm["libvirt_domain"]:
                    msg = "You have the same libvirt_domain listed twice in " \
                          "your pool ('%s' and '%s')." % (m_id, pm_id)
                    raise SlaveMachineError(msg)

            if self._pool_checks:
                available = False

                hostname = machine_spec["params"]["hostname"]
                if "rpc_port" in machine_spec["params"]:
                    port = machine_spec["params"]["rpc_port"]
                else:
                    port = lnst_config.get_option('environment', 'rpcport')

                logging.debug("Querying machine '%s': %s:%s" %\
                                                (m_id, hostname, port))
                if test_tcp_connection(hostname, port):
                    available = True

                if 'libvirt_domain' in machine_spec['params'] and \
                   not self._allow_virt:
                       logging.debug("libvirtd not running. Removing "\
                                     "libvirt_domain from machine '%s'" % m_id)
                       del machine_spec['params']['libvirt_domain']
            else:
                available = True

            if available:
                self._pool[m_id] = machine_spec
            return (m_id, available)

    def _process_machine_xml_data(self, m_id, machine_xml_data):
        machine_spec = {"interfaces": {}, "params":{}}

        # process parameters
        if "params" in machine_xml_data:
            for param in machine_xml_data["params"]:
                name = str(param["name"])
                value = str(param["value"])

                if name == "rpc_port":
                    machine_spec["params"][name] = int(value)
                else:
                    machine_spec["params"][name] = value

        mandatory_params = ["hostname"]
        for p in mandatory_params:
            if p not in machine_spec["params"]:
                msg = "Mandatory parameter '%s' missing for machine %s." \
                        % (p, m_id)
                raise SlaveMachineError(msg, machine_xml_data["params"])

        # process interfaces
        if "interfaces" in machine_xml_data:
            for iface in machine_xml_data["interfaces"]:
                if_id = iface["id"]
                iface_spec = self._process_iface_xml_data(m_id, iface)

                if if_id not in machine_spec["interfaces"]:
                    machine_spec["interfaces"][if_id] = iface_spec
                else:
                    msg = "Duplicate interface id '%s'." % if_id
                    raise SlaveMachineError(msg, iface)
        else:
            if "libvirt_domain" not in machine_spec["params"]:
                msg = "Machine '%s' has no testing interfaces. " \
                      "This setup is supported only for virtual slaves." \
                      % m_id
                raise SlaveMachineError(msg, machine_xml_data)

        return machine_spec

    def _process_iface_xml_data(self, m_id, iface):
        if_id = iface["id"]
        iface_spec = {"params": {}}
        iface_spec["network"] = iface["network"]

        for param in iface["params"]:
            name = str(param["name"])
            value = str(param["value"])

            if name == "hwaddr":
                iface_spec["params"][name] = normalize_hwaddr(value)
            else:
                iface_spec["params"][name] = value

        mandatory_params = ["hwaddr"]
        for p in mandatory_params:
            if p not in iface_spec["params"]:
                msg = "Mandatory parameter '%s' missing for machine %s, " \
                      "interface '%s'." % (p, m_id, if_id)
                raise SlaveMachineError(msg, iface["params"])

        return iface_spec

    def set_machine_requirements(self, mreqs):
        self._mreqs = mreqs
        self._mapper.set_requirements(mreqs)
        self._mapper.reset_match_state()

    def provision_machines(self, machines):
        """
        This method will try to map a dictionary of machines'
        requirements to a pool of machines that is available to
        this instance.

        :param templates: Setup request (dict of required machines)
        :type templates: dict

        :return: XML machineconfigs of requested machines
        :rtype: dict
        """


        mapper = self._mapper
        res = mapper.match()

        if not res and not mapper.get_virtual() and self._allow_virt:
            logging.info("Match failed for normal machines, falling back "\
                         "to matching virtual machines.")
            mapper.set_virtual(self._allow_virt)
            mapper.reset_match_state()
            res = mapper.match()

        if res:
            self._map = mapper.get_mapping()
        else:
            self._map = {}

        if self._map == {}:
            return False

        if self._map["virtual"]:
            mreqs = self._mreqs
            for m_id in self._map["machines"]:
                machines[m_id] = self._prepare_virtual_slave(m_id, mreqs[m_id])
        else:
            for m_id in self._map["machines"]:
                machines[m_id] = self._get_mapped_slave(m_id)

        return True

    def is_setup_virtual(self):
        return self._map["virtual"]

    def get_match(self):
        return self._map

    def _get_machine_mapping(self, m_id):
        return self._map["machines"][m_id]["target"]

    def _get_interface_mapping(self, m_id, if_id):
        return self._map["machines"][m_id]["interfaces"][if_id]

    def _get_network_mapping(self, net_id):
        return self._map["networks"][net_id]

    def _get_mapped_slave(self, tm_id):
        pm_id = self._get_machine_mapping(tm_id)
        pm = self._pool[pm_id]

        hostname = pm["params"]["hostname"]

        libvirt_domain = None
        if "libvirt_domain" in pm["params"]:
            libvirt_domain = pm["params"]["libvirt_domain"]

        rpcport = None
        if "rpc_port" in pm["params"]:
            rpcport = pm["params"]["rpc_port"]

        machine = Machine(tm_id, hostname, libvirt_domain, rpcport)

        used = []
        if_map = self._map["machines"][tm_id]["interfaces"]
        for t_if, p_if in if_map.iteritems():
            used.append(p_if)
            if_data = pm["interfaces"][p_if]

            for t_net, p_net in self._map["networks"].iteritems():
                if pm["interfaces"][p_if]["network"] == p_net:
                    break

            iface = machine.new_static_interface(t_if, "eth")
            iface.set_hwaddr(if_data["params"]["hwaddr"])
            iface.set_network(t_net)

        for if_id, if_data in pm["interfaces"].iteritems():
            if if_id not in used:
                iface = machine.new_unused_interface("eth")
                iface.set_hwaddr(if_data["params"]["hwaddr"])
                iface.set_network(t_net)

        return machine

    def _prepare_virtual_slave(self, tm_id, tm):
        pm_id = self._get_machine_mapping(tm_id)
        pm = self._pool[pm_id]

        hostname = pm["params"]["hostname"]
        libvirt_domain = pm["params"]["libvirt_domain"]

        rpcport = None
        if "rpc_port" in pm["params"]:
            rpcport = pm["params"]["rpc_port"]

        machine = Machine(tm_id, hostname, libvirt_domain, rpcport)

        # make all the existing unused
        for if_id, if_data in pm["interfaces"].iteritems():
            iface = machine.new_unused_interface("eth")
            iface.set_hwaddr(if_data["params"]["hwaddr"])
            iface.set_network(if_data["network"])

        # add all the other devices
        for if_id, if_data in tm["interfaces"].iteritems():
            iface = machine.new_virtual_interface(if_id, "eth")
            iface.set_network(if_data["network"])
            if "hwaddr" in if_data["params"]:
                iface.set_hwaddr(if_data["params"]["hwaddr"])
            if "driver" in if_data["params"]:
                iface.set_driver(if_data["params"]["driver"])

        return machine

class MapperError(Exception):
    pass

class SetupMapper(object):
    def __init__(self):
        self._pool = {}
        self._mreqs = {}
        self._unmatched_req_machines = []
        self._matched_pool_machines = []
        self._machine_stack = []
        self._net_label_mapping = {}
        self._virtual_matching = False

    def set_requirements(self, mreqs):
        self._mreqs = mreqs

    def set_pool(self, pool):
        self._pool = pool

    def set_virtual(self, virt_value):
        self._virtual_matching = virt_value

        for m_id, m in self._mreqs.iteritems():
            for if_id, interface in m["interfaces"].iteritems():
                if "params" in interface:
                    for name, val in interface["params"].iteritems():
                        if name not in ["hwaddr", "driver"]:
                            msg = "Dynamically created interfaces "\
                                  "only support the 'hwaddr' and 'driver' "\
                                  "option. '%s=%s' found on machine '%s' "\
                                  "interface '%s'" % (name, val,
                                                      m_id, if_id)
                            raise MapperError(msg)

    def get_virtual(self):
        return self._virtual_matching

    def reset_match_state(self):
        self._net_label_mapping = {}
        self._machine_stack = []
        self._unmatched_req_machines = self._mreqs.keys()

        self._unmatched_pool_machines = []
        for p_id, p_machine in self._pool.iteritems():
            if self._virtual_matching:
                if "libvirt_domain" in p_machine["params"]:
                    self._unmatched_pool_machines.append(p_id)
            else:
                self._unmatched_pool_machines.append(p_id)

        if self._pool is not None or self._mreqs is not None:
            self._push_machine_stack()

    def match(self):
        while len(self._machine_stack)>0:
            stack_top = self._machine_stack[-1]
            if self._virtual_matching and stack_top["virt_matched"]:
                if stack_top["current_match"] != None:
                    cur_match = stack_top["current_match"]
                    self._unmatched_pool_machines.append(cur_match)
                    stack_top["current_match"] = None
                stack_top["virt_matched"] = False

            if self._if_match():
                if len(self._unmatched_req_machines) > 0:
                    self._push_machine_stack()
                    continue
                else:
                    return True
            else:
                #unmap the pool machine
                if stack_top["current_match"] != None:
                    cur_match = stack_top["current_match"]
                    self._unmatched_pool_machines.append(cur_match)
                stack_top["current_match"] = None

                mreq_m_id = stack_top["m_id"]
                while len(stack_top["remaining_matches"]) > 0:
                    pool_m_id = stack_top["remaining_matches"].pop()
                    if self._check_machine_compatibility(mreq_m_id, pool_m_id):
                        #map compatible pool machine
                        stack_top["current_match"] = pool_m_id
                        pool_ifs = self._pool[pool_m_id]["interfaces"].keys()
                        stack_top["unmatched_pool_ifs"] = list(pool_ifs)

                        self._unmatched_pool_machines.remove(pool_m_id)
                        break

                if stack_top["current_match"] != None:
                    #clear if mapping
                    stack_top["if_stack"] = []
                    #next iteration will match the interfaces
                    if not self._virtual_matching:
                        self._push_if_stack()
                    continue
                else:
                    self._pop_machine_stack()
                    continue
        return False

    def _if_match(self):
        m_stack_top = self._machine_stack[-1]
        if_stack = m_stack_top["if_stack"]

        if self._virtual_matching:
            if m_stack_top["current_match"] != None:
                m_stack_top["virt_matched"] = True
                return True
            else:
                return False

        while len(if_stack) > 0:
            stack_top = if_stack[-1]

            req_m = self._mreqs[m_stack_top["m_id"]]
            pool_m = self._pool[m_stack_top["current_match"]]
            req_if = req_m["interfaces"][stack_top["if_id"]]
            req_net_label = req_if["network"]

            if stack_top["current_match"] != None:
                cur_match = stack_top["current_match"]
                m_stack_top["unmatched_pool_ifs"].append(cur_match)
                pool_if = pool_m["interfaces"][cur_match]
                pool_net_label = pool_if["network"]
                net_label_mapping = self._net_label_mapping[req_net_label]
                if net_label_mapping == (pool_net_label, m_stack_top["m_id"],
                                         stack_top["if_id"]):
                    del self._net_label_mapping[req_net_label]
            stack_top["current_match"] = None

            while len(stack_top["remaining_matches"]) > 0:
                pool_if_id = stack_top["remaining_matches"].pop()
                pool_if = pool_m["interfaces"][pool_if_id]
                if self._check_interface_compatibility(req_if, pool_if):
                    #map compatible interfaces
                    stack_top["current_match"] = pool_if_id
                    if req_net_label not in self._net_label_mapping:
                        self._net_label_mapping[req_net_label] =\
                                                   (pool_if["network"],
                                                   m_stack_top["m_id"],
                                                   stack_top["if_id"])
                    m_stack_top["unmatched_pool_ifs"].remove(pool_if_id)
                    break

            if stack_top["current_match"] != None:
                if len(m_stack_top["unmatched_ifs"]) > 0:
                    self._push_if_stack()
                    continue
                else:
                    return True
            else:
                self._pop_if_stack()
                continue
        return False

    def _push_machine_stack(self):
        machine_match = {}
        machine_match["m_id"] = self._unmatched_req_machines.pop()
        machine_match["current_match"] = None
        machine_match["remaining_matches"] = list(self._unmatched_pool_machines)
        machine_match["if_stack"] = []

        machine = self._mreqs[machine_match["m_id"]]
        machine_match["unmatched_ifs"] = machine["interfaces"].keys()
        machine_match["unmatched_pool_ifs"] = []

        if self._virtual_matching:
            machine_match["virt_matched"] = False

        self._machine_stack.append(machine_match)

    def _pop_machine_stack(self):
        stack_top = self._machine_stack.pop()
        self._unmatched_req_machines.append(stack_top["m_id"])

    def _push_if_stack(self):
        m_stack_top = self._machine_stack[-1]
        if_match = {}
        if_match["if_id"] = m_stack_top["unmatched_ifs"].pop()
        if_match["current_match"] = None
        if_match["remaining_matches"] = list(m_stack_top["unmatched_pool_ifs"])

        m_stack_top["if_stack"].append(if_match)

    def _pop_if_stack(self):
        m_stack_top = self._machine_stack[-1]
        if_stack_top = m_stack_top["if_stack"].pop()
        m_stack_top["unmatched_ifs"].append(if_stack_top["if_id"])

    def _check_machine_compatibility(self, req_id, pool_id):
        req_machine = self._mreqs[req_id]
        pool_machine = self._pool[pool_id]
        for param, value in req_machine["params"]:
            if param in pool_machine["params"] and\
               value != pool_machine["params"][param]:
                return False
        return True

    def _check_interface_compatibility(self, req_if, pool_if):
        label_mapping = self._net_label_mapping
        for req_label, mapping in label_mapping.iteritems():
            if req_label == req_if["network"] and\
               mapping[0] != pool_if["network"]:
                return False
            if mapping[0] == pool_if["network"] and\
               req_label != req_if["network"]:
                return False
        for param, value in req_if["params"]:
            if param in pool_if["params"] and\
               value != pool_if["params"][param]:
                return False
        return True

    def get_mapping(self):
        mapping = {"machines": {}, "networks": {}, "virtual": False}

        for req_label, label_map in self._net_label_mapping.iteritems():
            mapping["networks"][req_label] = label_map[0]

        for machine in self._machine_stack:
            m_map = mapping["machines"][machine["m_id"]] = {}
            m_map["target"] = machine["current_match"]
            interfaces = m_map["interfaces"] = {}
            if_stack = machine["if_stack"]
            for interface in if_stack:
                interfaces[interface["if_id"]] = interface["current_match"]


        if self._virtual_matching:
            mapping["virtual"] = True
        return mapping
