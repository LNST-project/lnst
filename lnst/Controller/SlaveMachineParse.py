"""
This module defines SlaveMachineParse class useful to parse XML machine
descriptions for the slave pool

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import os
import re
from lnst.Common.XmlProcessing import LnstParser
from lnst.Common.XmlProcessing import XmlDomTreeInit
from lnst.Common.XmlProcessing import XmlProcessingError
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Controller.RecipeParse import ParamsParse

class SlaveMachineParse(LnstParser):
    _machine_id = None
    _machine = None

    def set_machine(self, machine_id, machine):
        self._machine_id = machine_id
        self._machine = machine

    def parse(self, node):
        scheme = {"params": self._params,
                  "interfaces": self._interfaces}
        params = {"target": self._machine["params"]}
        self._process_child_nodes(node, scheme, params)

        self._machine["params"]["skip_cleanup"] = False
        mandatory_params = ["hostname"]
        for mandatory in mandatory_params:
            if mandatory not in self._machine["params"]:
                msg = "Missing required parameter '%s'" % mandatory
                raise XmlProcessingError(msg, node)

    def _params(self, node, params):
        subparser = ParamsParse(self)
        subparser.set_params_dict(params["target"])
        subparser.parse(node)

    def _interfaces(self, node, params):
        scheme = {"interface": self._interface,
                  "libvirt_create": self._libvirt_create}

        new_params = {"create": None}
        self._process_child_nodes(node, scheme, new_params)

    def _libvirt_create(self, node, params):
        scheme = {"interface": self._interface}

        new_params = {"create": "libvirt"}
        self._process_child_nodes(node, scheme, new_params)

    def _interface(self, node, params):
        machine = self._machine
        iface_id = self._get_attribute(node, "id")

        iface = machine["interfaces"][iface_id] = {}
        iface["create"] = params["create"]
        iface["network"] = self._get_attribute(node, "network")
        iface["params"] = {}

        # parse interface parameters
        scheme = {"params": self._params}
        params = {"target": iface["params"]}
        self._process_child_nodes(node, scheme, params)

        if "type" in iface["params"]:
            iface["type"] = iface["params"]["type"]
        else:
            msg = "Missing required parameter 'type'"
            raise XmlProcessingError(msg, node)

        # hwaddr parameter is optional for dynamic interface,
        # but it is required by non-dynamic interfaces
        if iface["create"] and "hwaddr" in iface["params"]:
                iface["hwaddr"] = normalize_hwaddr(iface["params"]["hwaddr"])
        else:
            if "hwaddr" in iface["params"]:
                iface["hwaddr"] = normalize_hwaddr(iface["params"]["hwaddr"])
            else:
                msg = "Missing required parameter 'hwaddr'"
                raise XmlProcessingError(msg, node)

        # name parameter is only valid when the interface is not dynamic
        if "name" in iface["params"]:
            if iface["create"]:
                msg = "'name' parameter is not valid with dynamic interfaces"
                raise XmlProcessingError(msg, node)
            else:
                iface["name"] = iface["params"]["name"]

        # bridge parameter is valid only when the interface is dynamic
        if "libvirt_bridge" in iface["params"]:
            if iface["create"] == "libvirt":
                iface["libvirt_bridge"] = iface["params"]["libvirt_bridge"]
            else:
                msg = "'libvirt_bridge' parameter is not valid with" \
                      "dynamic ifaceices"
                raise XmlProcessingError(msg, node)
