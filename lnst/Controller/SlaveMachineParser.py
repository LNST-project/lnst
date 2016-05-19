"""
This module defines SlaveMachineParser class useful to parse XML machine
descriptions for the slave pool

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import os
from lnst.Controller.XmlParser import XmlParser
from lnst.Controller.XmlProcessing import XmlProcessingError, XmlData
from lnst.Controller.XmlProcessing import XmlCollection

class SlaveMachineError(XmlProcessingError):
    pass

class SlaveMachineParser(XmlParser):
    def __init__(self, sm_path):
        super(SlaveMachineParser, self).__init__("schema-sm.rng", sm_path)

    def _process(self, sm_tag):
        sm = XmlData(sm_tag)

        # params
        params_tag = sm_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            sm["params"] = params

        # interfaces
        interfaces_tag = sm_tag.find("interfaces")
        if interfaces_tag is not None and len(interfaces_tag) > 0:
            sm["interfaces"] = XmlCollection(interfaces_tag)
            for eth_tag in interfaces_tag:
                interface = self._process_interface(eth_tag)
                sm["interfaces"].append(interface)

        security_tag = sm_tag.find("security")
        sm["security"] = self._process_security(security_tag)
        return sm

    def _process_params(self, params_tag):
        params = XmlCollection(params_tag)
        if params_tag is not None:
            for param_tag in params_tag:
                param = XmlData(param_tag)
                param["name"] = self._get_attribute(param_tag, "name")
                param["value"] = self._get_attribute(param_tag, "value")
                params.append(param)
        return params

    def _process_interface(self, iface_tag):
        iface = XmlData(iface_tag)
        iface["id"] = self._get_attribute(iface_tag, "id")
        iface["network"] = self._get_attribute(iface_tag, "label")
        iface["type"] = "eth"

        # interface parameters
        params_tag = iface_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            iface["params"] = params

        return iface

    def _process_security(self, sec_tag):
        sec = XmlData(sec_tag)

        if sec_tag is None:
            sec["auth_type"] = "none"
            return sec

        auth_type_tag = sec_tag.find("auth_type")
        sec["auth_type"] = auth_type_tag.text.strip()

        auth_passwd_tag = sec_tag.find("auth_password")
        if auth_passwd_tag is not None:
            sec["auth_passwd"] = auth_passwd_tag.text
        else:
            sec["auth_passwd"] = ""

        key_tag = sec_tag.find("pubkey_path")
        if key_tag is not None:
            path = key_tag.text
            exp_path = os.path.expanduser(path)
            abs_path = os.path.join(os.path.dirname(self._path), exp_path)
            norm_path = os.path.normpath(abs_path)
            sec["pubkey_path"] = norm_path
        else:
            sec["pubkey_path"] = ""

        return sec
