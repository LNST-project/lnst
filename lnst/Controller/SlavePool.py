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
from lnst.Common.XmlProcessing import XmlProcessingError, XmlData
from lnst.Controller.Machine import Machine
from lnst.Controller.SlaveMachineParser import SlaveMachineParser
from lnst.Controller.SlaveMachineParser import SlaveMachineError

class SlavePool:
    """
    This class is responsible for managing test machines that
    are available at the controler and can be used for testing.
    """

    _map = {}
    _pool = {}

    _machine_matches = []
    _network_matches = []

    _allow_virt = False
    _pool_checks = True

    def __init__(self, pool_dirs, allow_virtual=False, pool_checks=True):
        self._allow_virt = allow_virtual
        self._pool_checks = pool_checks
        for pool_dir in pool_dirs:
            self.add_dir(pool_dir)

    def add_dir(self, pool_dir):
        dentries = os.listdir(pool_dir)

        for dirent in dentries:
            self.add_file("%s/%s" % (pool_dir, dirent))

    def add_file(self, filepath):
        if os.path.isfile(filepath) and re.search("\.xml$", filepath, re.I):
            dirname, basename = os.path.split(filepath)
            m_id = re.sub("\.[xX][mM][lL]$", "", basename)

            parser = SlaveMachineParser(filepath)
            xml_data = parser.parse()
            machine_spec = self._process_machine_xml_data(m_id, xml_data)

            if self._pool_checks:
                hostname = machine_spec["params"]["hostname"]
                if "rpcport" in machine_spec:
                    port = machine_spec["params"]["rpcport"]
                else:
                    port = lnst_config.get_option('environment', 'rpcport')

                logging.info("Querying slave machine %s." % m_id)
                if not test_tcp_connection(hostname, port):
                    msg = "Machine '%s' not responding. Skipping." % m_id
                    logging.warning(msg)
                    return

                if 'libvirt_domain' in machine_spec['params'] and \
                   not self._allow_virt:
                    msg = "libvird not running. Skipping machine '%s'." % m_id
                    logging.warning(msg)

            logging.info("Adding slave machine %s to slave pool." % m_id)
            self._pool[m_id] = machine_spec

    def _process_machine_xml_data(self, m_id, machine_xml_data):
        machine_spec = {"interfaces": {}, "params":{}}

        # process parameters
        if "params" in machine_xml_data:
            for param in machine_xml_data["params"]:
                name = str(param["name"])
                value = str(param["value"])
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

    def provision_machines(self, mreqs, machines):
        """
        This method will try to map a dictionary of machines'
        requirements to a pool of machines that is available to
        this instance.

        :param templates: Setup request (dict of required machines)
        :type templates: dict

        :return: XML machineconfigs of requested machines
        :rtype: dict
        """

        mapper = SetupMapper()
        self._map = mapper.map_setup(mreqs, self._pool)

        if self._map == None:
            return False

        if self._map["virtual"]:
            for m_id in self._map["machines"]:
                machines[m_id] = self._prepare_virtual_slave(m_id, mreqs[m_id])
        else:
            for m_id in self._map["machines"]:
                machines[m_id] = self._get_mapped_slave(m_id)

        return True

    def is_setup_virtual(self):
        return self._map["virtual"]

    def get_provisioner_id(self, m_id):
        try:
            return self._get_machine_mapping(m_id)
        except KeyError:
            return None

    def get_provisioner(self, m_id):
        try:
            p_id = self._get_machine_mapping(m_id)
            return self._pool[p_id]
        except KeyError:
            return None

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

        machine = Machine(tm_id, hostname, libvirt_domain)

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

        machine = Machine(tm_id, hostname, libvirt_domain)

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

        return machine

class MapperError(Exception):
    pass

class SetupMapper:
    """
    This class can be used for matching machine setups against
    a pool of interconnected machines. SetupMapper will search
    through the pool for suitable matches of the requested
    setup and return the mapping between the two.

    Here we explain some terminology that is used consistently
    through the whole class:

        nc = neighbour connection; a 3-tuple that describes connection
             to an adjacent machine with the information which interface
             is used.

             (neighbour_id, network_id, iface_id)

        nc_list = list of neighbour connections; it is a building block
                  of a topology

        topology = dictionary of nc_lists; it is an analogy to a adjacency
                   list -- represenation of a graph. It is modified so it's
                   able to represent non-graph structures such as our
                   topology

        match = a correspondence between a machine, interface or a network
                from template and from a pool. It's a 2-tuple.

                (template_machine, pool_machine)
                (template_machines_iface, pool_machines_iface)
                (template_network, pool_network)
    """

    _machine_map = None
    _iface_map = None
    _network_map = None

    _template_machines = None
    _pool_machines = None

    @staticmethod
    def _get_topology(machine_desc):
        """
        This function will generate an adjacenty list from machine
        configuration dictionary. It can handle both machines and
        templates.

        :param machine_desc: dictionary of machines in the topology
        :type machines_configs: dict

        :return: Topology - neighbour connection list (adjacency list-like
            data structure
        :rtype: dict
        """

        networks = {}
        for m_id, m_config in machine_desc.iteritems():
            for dev_id, dev_info in m_config["interfaces"].iteritems():
                net = dev_info["network"]
                if not net in networks:
                    networks[net] = []
                networks[net].append((m_id, dev_id))

        topology = {}
        for m_id, m_config in machine_desc.iteritems():
            topology[m_id] = []
            for net_name, net in networks.iteritems():
                devs_in_net = []
                for dev_id, dev_info in m_config["interfaces"].iteritems():
                    if dev_info["network"] == net_name:
                        devs_in_net.append(dev_id)

                net_in_use = False
                for neighbour in net:
                    n_m_id = neighbour[0]
                    n_dev_id = neighbour[1]
                    if n_m_id != m_id:
                        net_in_use = True
                        for dev_in_net in devs_in_net:
                            nc = (n_m_id, net_name, dev_in_net)
                            if not nc in topology[m_id]:
                                topology[m_id].append(nc)

                if not net_in_use:
                    msg = "Network '%s' contains only one machine!" % net_name
                    raise MapperError(msg)

        return topology

    @staticmethod
    def _is_match_valid(template_id, pool_id, matches):
        for match in matches:
            if (match[0] == template_id and match[1] != pool_id) or \
               (match[0] != template_id and match[1] == pool_id):
                return False

        return True

    def _is_machine_match_valid(self, template_id, pool_id):
        """
        Method for checking validity of a proposed match between
        two machines.

        :param template_id: machine id in template setup
        :type template_id: string

        :param pool_id: machine id in pool setup
        :type pool_id: string

        :return: True/False indicating the validity of this match
        :rtype: Bool
        """

        template_machine = self._template_machines[template_id]
        pool_machine = self._pool_machines[pool_id]

        # check machine properties
        for prop_name, prop_value in template_machine["params"].iteritems():
            if prop_name not in pool_machine["params"] or\
               pool_machine["params"][prop_name] != prop_value:
                return False

        # check number of devices
        tm_ndevs = len(template_machine["interfaces"])
        pm_ndevs = len(pool_machine["interfaces"])
        if tm_ndevs > pm_ndevs:
            return False

        return self._is_match_valid(template_id, pool_id,
                                    self._machine_map)

    def _is_network_match_valid(self, template_id, pool_id):
        """
        Method for checking validity of a proposed match between
        two network names.

        :param template_id: network id in template setup
        :type template_id: string

        :param pool_id: network id in pool setup
        :type pool_id: string

        :return: True/False indicating the validity of this match
        :rtype: Bool
        """

        return self._is_match_valid(template_id, pool_id,
                                    self._network_map)

    def _is_if_match_valid(self, tm_id, t_if_id, pm_id, pm_if_id):
        """
        Check if matching of one interface on another is valid.
        This functions checks the parameters of those two interfaces,
        such as type, mac address etc.

        :param tm_id: template machine id
        :type tm_id: string

        :param tm_if_id: template machine's interface id
        :type tm_if_id: string

        :param pm_id: pool machine id
        :type tm_id: string

        :param pm_if_id: pool machine's interface id
        :type pm_if_id: string

        :return: True/False indicating the validity of this match
        :rtype: Bool
        """

        t_if = self._template_machines[tm_id]["interfaces"][t_if_id]
        p_if = self._pool_machines[pm_id]["interfaces"][pm_if_id]


        for prop_name, prop_value in t_if["params"].iteritems():
            if p_if["params"][prop_name] != prop_value:
                return False

        properties = ["type"]
        for prop_name, prop_value in t_if.iteritems():
            if prop_name in properties:
                if p_if[prop_name] != prop_value:
                    return False

        return True

    @staticmethod
    def _get_node_with_most_neighbours(topology):
        max_machine = None
        max_len = 0
        for machine, nc_list in topology.iteritems():
            if len(nc_list) > max_len:
                max_machine = machine
                max_len = len(nc_list)

        return max_machine

    def _get_possible_matches(self, machine, pool_topology):
        possible_matches = set(pool_topology.keys())
        impossible_matches = set()

        for match in self._machine_map:
            if match[0] == machine and not match[1] in impossible_matches:
                # in case the machine has already been matched,
                # return the corresponding match as an only option
                return set([match[1]])
            else:
                # in case the machine has been matched to a different
                # one in pool, remove it from possible matches
                impossible_matches.add(match[1])

        return possible_matches - impossible_matches

    def _get_nc_matches(self, tm_id, tm_nc_list, pm_id, pm_nc_list):
        """
        Return all possible ways of matching list of neighbours of a template
        machine on another list of neighbours of a pool machine. This function
        also keeps in mind what matches already exist and avoids conflicts.

        :param tm_nc_list: short for template machine neighbour connection list
        :type tm_nc_list: list

        :param pm_nc_list: short for pool machine neighbour connection list
        :type pm_nc_list: list

        :return: List of all possible mapping updates that are result of a
            successful matching between the machine's neighbour connections.
        :rtype: list
        """

        mmap = self._machine_map
        nmap = self._network_map
        mapping_update = []

        t_neigh, t_net, t_if = tm_nc_list[0]

        # recursion stop condition
        if len(tm_nc_list) == 1:
            for nc in pm_nc_list:
                p_neigh, p_net, p_if = nc
                if self._is_machine_match_valid(t_neigh, p_neigh) and \
                   self._is_network_match_valid(t_net, p_net) and \
                   self._is_if_match_valid(tm_id, t_if, pm_id, p_if):
                    mapping = self._get_mapping_update(tm_nc_list[0], nc)
                    mapping_update.append(mapping)

            return mapping_update

        for nc in pm_nc_list:
            p_neigh, p_net, p_if = nc
            if self._is_machine_match_valid(t_neigh, p_neigh) and \
               self._is_network_match_valid(t_net, p_net) and \
               self._is_if_match_valid(tm_id, t_if, pm_id, p_if):
                recently_added = self._get_mapping_update(tm_nc_list[0], nc)
                self._save_nc_match(recently_added)

                new_pm_nc_list = copy.deepcopy(pm_nc_list)
                new_pm_nc_list.remove(nc)

                possible_matches = self._get_nc_matches(tm_id, tm_nc_list[1:],
                                                        pm_id, new_pm_nc_list)
                self._revert_nc_match(recently_added)
                for possible_match in possible_matches:
                    mapping = (recently_added[0] + possible_match[0],
                               recently_added[1] + possible_match[1],
                               recently_added[2] + possible_match[2])
                    mapping_update.append(mapping)

        return mapping_update

    def _get_mapping_update(self, template_nc, pool_nc):
        i = [(template_nc[2], pool_nc[2])]

        m = []
        m_match = (template_nc[0], pool_nc[0])
        if not m_match in self._machine_map:
            m.append(m_match)

        n = []
        n_match = (template_nc[1], pool_nc[1])
        if not n_match in self._network_map:
            n.append(n_match)

        return (i, m, n)

    def _save_nc_match(self, nc_match):
        self._machine_map |= set(nc_match[1])
        self._network_map |= set(nc_match[2])

    def _revert_nc_match(self, nc_match):
        self._machine_map -= set(nc_match[1])
        self._network_map -= set(nc_match[2])

    def _format_map_dict(self, machine_map, network_map):
        map_dict = {}

        map_dict["machines"] = {}
        for match in machine_map:
            if_map = {}
            for if_match in match[2]:
                if_map[if_match[0]] = if_match[1]
            map_dict["machines"][match[0]] = {"target": match[1],
                                              "interfaces": if_map}

        map_dict["networks"] = {}
        for match in network_map:
            map_dict["networks"][match[0]] = match[1]

        return map_dict

    def map_setup(self, template_machines, pool_machines):
        """
        Attempt to match template topology to pool topology.

        :param template_topology: dictionary of machine templates to be matched
            against the pool
        :type template_topology: dict

        :param pool_topology: dictionary o machine structures that will be used
            as a pool of available machines
        :type pool_topology: dict

        :return: 2-tuple (machine_map, network_map). Machine map is a list of
            3-tuples (template_machine_id, pool_machine_id, iface_map),
            both iface_map and network_map are list of mappings between
            matched equivalents in template and pool.
        :rtype: tuple containing machine and network mappings
        """

        self._machine_map = set()
        self._iface_map = {}
        self._network_map = set()

        self._template_machines = template_machines
        self._pool_machines = pool_machines

        template_topology = self._get_topology(template_machines)
        pool_topology = self._get_topology(pool_machines)

        for m, cons in template_topology.iteritems():
            if len(cons) == 0:
                msg = "Isolated machine in template topology: '%s'" % m
                raise MapperError(msg)

        if self._map_setup(template_topology, pool_topology):
            machine_map = [(tm, pm, self._iface_map[tm]) \
                            for tm, pm in self._machine_map]
            network_map = list(self._network_map)
            mmap = self._format_map_dict(machine_map, network_map)
            mmap["virtual"] = False
            return mmap
        elif self._map_setup_virt(template_machines, pool_machines):
            machine_map = [(tm, pm, []) for tm, pm in self._machine_map]
            mmap = self._format_map_dict(machine_map, [])
            mmap["virtual"] = True
            return mmap
        else:
            return None

    def _map_setup(self, template_topology, pool_topology):

        if len(template_topology) <= 0:
            return True

        mmap = self._machine_map
        nmap = self._network_map

        # by choosing to match the biggest nodes in the topology first,
        # we optimize the amount of time it takes to find out that the
        # topology cannot be matched (in most cases)
        machine = self._get_node_with_most_neighbours(template_topology)

        possible_matches = self._get_possible_matches(machine, pool_topology)
        for possible_match in possible_matches:
            if not self._is_match_valid(machine, possible_match, mmap):
                continue

            mmap.add((machine, possible_match))

            template_nc_list = template_topology[machine]
            pool_nc_list = pool_topology[possible_match]

            nc_matches = self._get_nc_matches(machine, template_nc_list,
                                                possible_match, pool_nc_list)
            for nc_match in nc_matches:
                self._save_nc_match(nc_match)
                self._iface_map[machine] = nc_match[0]

                new_pool = copy.deepcopy(pool_topology)
                del new_pool[possible_match]

                new_template = copy.deepcopy(template_topology)
                del new_template[machine]

                if not self._map_setup(new_template, new_pool):
                    self._revert_nc_match(nc_match)
                    del self._iface_map[machine]
                    continue
                else:
                    return True

            mmap.discard((machine, possible_match))

        return False

    def _machine_matches(self, tm, pm):
        for prop_name, prop_value in tm["params"].iteritems():
            if prop_name not in pm["params"] or\
               pm["params"][prop_name] != prop_value:
                return False

        return True

    def _map_setup_virt(self, template_machines, pool_machines):
        available = set()
        matches = set()
        for m_id in pool_machines.iterkeys():
            available.add(m_id)

        for tm_id, tm in template_machines.iteritems():
            match = None
            for am_id in available:
                if self._machine_matches(tm, pool_machines[am_id]):
                    match = (tm_id, am_id)
                    available.remove(am_id)
                    break

            if match:
                matches.add(match)
            else:
                return False

        self._machine_map = list(matches)
        return True
