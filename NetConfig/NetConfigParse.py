"""
This module defines NetConfigParse class useful to parse xml configs

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

from xml.dom.minidom import parseString
import logging
from NetConfigDevNames import NetConfigDevNames
from NetConfigDevNames import normalize_hwaddr
from NetConfigCommon import get_slaves

class NetConfigParse:
    def __init__(self, machine_xml_string):
        self._machine_xml_string = machine_xml_string
        netdevs, info = self.parse_machine_config(machine_xml_string)
        self._machine_netdevs = netdevs
        self._machine_info = info

    def get_machine_netdevs(self):
        return self._machine_netdevs

    def get_machine_info(self):
        return self._machine_info

    def _parse_machine_config(self, machine_xml_string, callback=None):
        dom = parseString(machine_xml_string)
        dom_netmachine = dom.getElementsByTagName("netmachineconfig")[0]

        dom_info = dom_netmachine.getElementsByTagName("info")[0]
        hostname = str(dom_info.getAttribute("hostname"))
        rootpass = str(dom_info.getAttribute("rootpass"))
        rpcport = str(dom_info.getAttribute("rpcport"))
        info = {"hostname": hostname}
        if rootpass:
            info["rootpass"] = rootpass
        if rpcport:
            info["rpcport"] = int(rpcport)
        info["system_config"] = {}

        dom_netdevs = dom_netmachine.getElementsByTagName("netdevice")
        netdevs = {}
        for dom_netdev in dom_netdevs:
            dev_pid = int(dom_netdev.getAttribute("phys_id"))
            dev_type = str(dom_netdev.getAttribute("type"))
            dev_hwaddr = str(dom_netdev.getAttribute("hwaddr"))
            dev_hwaddr = normalize_hwaddr(dev_hwaddr)
            dev_name = str(dom_netdev.getAttribute("name"))
            netdevs[dev_pid] = {"type": dev_type, "hwaddr": dev_hwaddr}
            netdev = netdevs[dev_pid]
            if dev_name:
                netdev["name"] = dev_name
            if callback:
                callback(dev_pid, netdev, dom_netdev)
        return netdevs, info, dom

    def parse_machine_config(self, machine_xml_string):
        return self._parse_machine_config(machine_xml_string)[0:2]

    def _refresh_machine_config_cb(self, dev_pid, netdev, dom_netdev):
        if "name" in netdev:
            del netdev["name"]
        self._dev_names.assign_name_by_scan(dev_pid, netdev)
        dom_netdev.setAttribute("name", netdev["name"])

    def refresh_machine_config(self):
        self._dev_names = NetConfigDevNames()
        dom = self._parse_machine_config(self._machine_xml_string,
                                         self._refresh_machine_config_cb)[2]
        return dom.toxml()

    def parse_config(self, net_xml_string):
        dom = parseString(net_xml_string)
        dom_netconfig = dom.getElementsByTagName("netconfig")[0]
        dom_netdevs = dom_netconfig.getElementsByTagName("netdevice")
        config = {}
        for dom_netdev in dom_netdevs:
            self._parse_netdevice(config, dom_netdev)
        self._check_slave_references(config)
        return config

    def _parse_list(self, netdev, dom_netdev, config,
                    itemname, groupname, handler, container):
        dom_list1 = dom_netdev.getElementsByTagName(groupname)
        if dom_list1:
            netdev[groupname] = container
        for dom_item1 in dom_list1:
            dom_list2 = dom_item1.getElementsByTagName(itemname)
            for dom_item2 in dom_list2:
                handler(netdev[groupname], dom_item2, config)

    def _parse_options_handler(self, lst, dom_element, config):
        name = str(dom_element.getAttribute("name"))

        value = ""
        if dom_element.hasAttribute("value"):
            value = str(dom_element.getAttribute("value"))
        elif dom_element.hasChildNodes():
            node = dom_element.firstChild
            try:
                value = str(dom_element.firstChild.data)
            except:
                raise Exception("Invalid option value")

        lst.append((name, value))

    def _parse_options(self, netdev, dom_netdev, config):
        self._parse_list(netdev, dom_netdev, config, "option", "options",
                         self._parse_options_handler, [])

    def _check_slave(self, dev_id, config):
        for key in config:
            netdev = config[key]
            if dev_id in get_slaves(netdev):
                logging.warn("netdev id \"%d\" used as slave for "
                         "netdev id \"%d\" as well" % (dev_id, key))

    def _check_slave_references(self, config):
        for key in config:
            netdev = config[key]
            for slave in get_slaves(netdev):
                if not slave in config:
                    logging.error("netdev id \"%d\" references nonexistent "
                                  "slave with id \"%d\"" % (key, slave))
                    raise Exception

    def _parse_slaves_handler(self, lst, dom_element, config):
        dev_id = int(dom_element.getAttribute("id"))
        self._check_slave(dev_id, config)
        lst.append(dev_id)

    def _parse_slaves(self, netdev, dom_netdev, config):
        self._parse_list(netdev, dom_netdev, config, "slave", "slaves",
                         self._parse_slaves_handler, [])

    def _parse_addrs_handler(self, lst, dom_element, config):
        lst.append(str(dom_element.getAttribute("value")))

    def _parse_addresses(self, netdev, dom_netdev, config):
        self._parse_list(netdev, dom_netdev, config, "address", "addresses",
                        self._parse_addrs_handler, [])

    def _check_phys_id(self, dev_pid, config):
        for key in config:
            if not "phys_id" in config[key]:
                continue
            if config[key]["phys_id"] == dev_pid:
                logging.error("same phys_id \"%d\" used more than once" % dev_pid)
                raise Exception

    def _parse_phys_id(self, netdev, dom_netdev, config):
        dev_pid = dom_netdev.getAttribute("phys_id")
        if not dev_pid:
            return
        dev_pid = int(dev_pid)

        if netdev["type"] != "eth":
            logging.warn("phys_id found on non-eth netdev, ignoring")
            return

        self._check_phys_id(dev_pid, config)

        netdev["phys_id"] = dev_pid
        if dev_pid in self._machine_netdevs:
            entry = self._machine_netdevs[dev_pid]
            if entry["type"] == netdev["type"]:
                netdev["hwaddr"] = entry["hwaddr"]
                if "name" in entry:
                    netdev["name"] = entry["name"]
        else:
            logging.error("phys_id passed but does not match any device on machine")
            raise Exception

    def _parse_netdevice(self, config, dom_netdev):
        dev_id = int(dom_netdev.getAttribute("id"))
        logging.debug("Parsing netdev id \"%d\"" % dev_id)
        if dev_id in config:
            logging.error("netdev id used more than once")
            raise Exception
        config[dev_id] = {}
        netdev = config[dev_id]
        netdev["type"] = dev_type = str(dom_netdev.getAttribute("type"))

        self._parse_phys_id(netdev, dom_netdev, config)
        self._parse_addresses(netdev, dom_netdev, config)

        if dev_type == "eth":
            pass
        elif dev_type in ["bond", "bridge", "vlan", "macvlan", "team"]:
            self._parse_options(netdev, dom_netdev, config)
            self._parse_slaves(netdev, dom_netdev, config)
        else:
            logging.warn("unknown type \"%s\"" % dev_type)
