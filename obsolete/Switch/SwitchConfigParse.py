"""
This module defines SwitchConfigParse class useful to parse switch xml configs

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

from xml.dom.minidom import parseString
import logging

class SwitchConfigParse:
    def __init__(self):
        pass

    def get_switch_info(self):
        return self._machine_info

    def _parse_list(self, result, dom_element, itemname, groupname,
                    handler, container):
        dom_list1 = dom_element.getElementsByTagName(groupname)
        if dom_list1:
            result[groupname] = container
        for dom_item1 in dom_list1:
            dom_list2 = dom_item1.getElementsByTagName(itemname)
            for dom_item2 in dom_list2:
                handler(result[groupname], dom_item2)

    def _parse_vlan_ports_handler(self, dct, dom_element):
        port_id = int(dom_element.getAttribute("id"))
        tagged = str(dom_element.getAttribute("tagged"))
        if tagged == "yes":
            tagged = True
        elif tagged == "no":
            tagged = False
        else:
            raise Exception
        dct[port_id] =  {"tagged": tagged}

    def _parse_vlan_ports(self, result, dom_element):
        self._parse_list(result, dom_element, "port", "ports",
                         self._parse_vlan_ports_handler, {})

    def _parse_vlans_handler(self, dct, dom_element):
        name = str(dom_element.getAttribute("name"))
        vlan_tci = str(dom_element.getAttribute("vlan_tci"))
        vlan = {"name": name}
        self._parse_vlan_ports(vlan, dom_element)
        dct[vlan_tci] = vlan

    def _parse_vlans(self, result, dom_element):
        self._parse_list(result, dom_element, "vlan", "vlans",
                         self._parse_vlans_handler, {})

    def parse_switch_config(self, xml_string):
        config = {}
        dom = parseString(xml_string)
        dom_switch = dom.getElementsByTagName("netswitchconfig")[0]

        dom_info = dom_switch.getElementsByTagName("info")[0]
        hostname = str(dom_info.getAttribute("hostname"))
        port = str(dom_info.getAttribute("port"))
        driver = str(dom_info.getAttribute("driver"))
        info = {"hostname": hostname, "driver": driver}
        if port:
            info["port"] = int(port)
        config["info"] = info
        self._parse_vlans(config, dom_switch)
        return config
