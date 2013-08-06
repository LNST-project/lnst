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
from lnst.Controller.RecipeParse import ParamsParse
from lnst.Common.XmlParser import LnstParser
from lnst.Common.XmlProcessing import XmlDomTreeInit, XmlProcessingError
from lnst.Common.XmlProcessing import XmlData, XmlCollection

class SlaveMachineError(XmlProcessingError):
    pass

class SlaveMachineParse(LnstParser):
    def parse(self, node):
        self._data = XmlData(node)
        scheme = {"params": self._params,
                  "interfaces": self._interfaces}
        self._process_child_nodes(node, scheme)
        return self._data

    def _params(self, node, params):
        if "params" in self._data:
            msg = "Only a single <params> child allowed under <slavemachine>."
            raise SlaveMachineError(msg, node)

        subparser = ParamsParse(self)
        self._data["params"] = subparser.parse(node)

    def _interfaces(self, node, params):
        if not "interfaces" in self._data:
            self._data["interfaces"] = XmlCollection(node)
        else:
            msg = "Only a single <interfaces> child allowed under <slavemachine>."
            raise SlaveMachineError(msg, node)

        scheme = {"eth": self._eth}
        self._process_child_nodes(node, scheme)

    def _eth(self, node, params):
        machine = self._data

        iface = XmlData(node)
        iface["id"] = self._get_attribute(node, "id")
        iface["network"] = self._get_attribute(node, "network")
        iface["type"] = "eth"

        # parse interface parameters
        scheme = {"params": self._iface_params}
        params = {"iface": iface}
        self._process_child_nodes(node, scheme, params)

        machine["interfaces"].append(iface)

    def _iface_params(self, node, params):
        if "params" in params["iface"]:
            msg = "Only a single <params> child allowed under <interface>."
            raise SlaveMachineError(msg, node)

        subparser = ParamsParse(self)
        params["iface"]["params"] = subparser.parse(node)
