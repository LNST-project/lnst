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
from lnst.Controller.NetTestParse import ParamsParse

class SlaveMachineParse(LnstParser):
    _machine_id = None
    _machine = None

    def set_machine(self, machine_id, machine):
        self._machine_id = machine_id
        self._machine = machine

    def parse(self, node):
        scheme = {"params": self._params,
                  "netdevices": self._netdevices}
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

    def _netdevices(self, node, params):
        scheme = {"netdevice": self._netdevice,
                  "libvirt_create": self._libvirt_create}

        new_params = {"create": None}
        self._process_child_nodes(node, scheme, new_params)

    def _libvirt_create(self, node, params):
        scheme = {"netdevice": self._netdevice}

        new_params = {"create": "libvirt"}
        self._process_child_nodes(node, scheme, new_params)

    def _netdevice(self, node, params):
        machine = self._machine
        phys_id = self._get_attribute(node, "phys_id")

        dev = machine["netdevices"][phys_id] = {}
        dev["create"] = params["create"]
        dev["network"] = self._get_attribute(node, "network")
        dev["params"] = {}

        # parse device parameters
        scheme = {"params": self._params}
        params = {"target": dev["params"]}
        self._process_child_nodes(node, scheme, params)

        if "type" in dev["params"]:
            dev["type"] = dev["params"]["type"]
        else:
            msg = "Missing required parameter 'type'"
            raise XmlProcessingError(msg, node)

        # hwaddr parameter is optional for dynamic devices,
        # but it is required by non-dynamic devices
        if dev["create"] and "hwaddr" in dev["params"]:
                dev["hwaddr"] = normalize_hwaddr(dev["params"]["hwaddr"])
        else:
            if "hwaddr" in dev["params"]:
                dev["hwaddr"] = normalize_hwaddr(dev["params"]["hwaddr"])
            else:
                msg = "Missing required parameter 'hwaddr'"
                raise XmlProcessingError(msg, node)

        # name parameter is only valid when the device is not dynamic
        if "name" in dev["params"]:
            if dev["create"]:
                msg = "'name' parameter is not valid with dynamic devices"
                raise XmlProcessingError(msg, node)
            else:
                dev["name"] = dev["params"]["name"]

        # bridge parameter is valid only when the device is dynamic
        if "libvirt_bridge" in dev["params"]:
            if dev["create"] == "libvirt":
                dev["libvirt_bridge"] = dev["params"]["libvirt_bridge"]
            else:
                msg = "'libvirt_bridge' parameter is not valid with" \
                      "dynamic devices"
                raise XmlProcessingError(msg, node)

        try:
            self._trigger_event("netdevice_ready",
                    {"machine_id": self._machine_id, "dev_id": phys_id})
        except Exception as exc:
            logging.error(XmlProcessingError(str(exc), node))
            raise
