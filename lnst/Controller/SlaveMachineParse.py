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
        scheme = {"eth": self._eth}

        try:
            self._process_child_nodes(node, scheme)
        except XmlProcessingError as err:
            msg = "Interface type other than 'eth' is not allowed here. " \
                  "Other types must be configured in LNST recipes directly."
            logging.error(msg)
            raise

    def _eth(self, node, params):
        machine = self._machine
        iface_id = self._get_attribute(node, "id")

        iface = machine["interfaces"][iface_id] = {}
        iface["network"] = self._get_attribute(node, "network")
        iface["params"] = {}
        iface["type"] = "eth"

        # parse interface parameters
        scheme = {"params": self._params}
        params = {"target": iface["params"]}
        self._process_child_nodes(node, scheme, params)

        if "hwaddr" in iface["params"]:
            iface["hwaddr"] = normalize_hwaddr(iface["params"]["hwaddr"])
        else:
            msg = "Missing required parameter 'hwaddr'"
            raise XmlProcessingError(msg, node)

        if "name" in iface["params"]:
            iface["name"] = iface["params"]["name"]
