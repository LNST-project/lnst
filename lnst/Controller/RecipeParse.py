"""
This module defines RecipeParse class useful to parse xml recipes

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import os
import re
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.Utils import bool_it
from lnst.Common.RecipePath import RecipePath
from lnst.Common.XmlProcessing import XmlDomTreeInit, XmlProcessingError
from lnst.Common.XmlProcessing import XmlData, XmlCollection
from lnst.Common.XmlParser import LnstParser

class RecipeError(XmlProcessingError):
    pass

class RecipeParse(LnstParser):
    def __init__(self, recipe_filepath):
        super(RecipeParse, self).__init__()

        self._filepath = recipe_filepath
        self._rp = RecipePath(None, self._filepath)
        self._include_root = self._rp.get_root()

    def parse_recipe(self):
        dom_init = XmlDomTreeInit()
        rp = self._rp
        self._xml_dom = node = dom_init.parse_string(rp.to_str(), rp.abs_path())

        if node.nodeType == node.DOCUMENT_NODE:
            scheme = {"lnstrecipe": self._lnstrecipe}
            self._process_child_nodes(node, scheme)
        else:
            raise ValueError("Passed object is not a XML document")

        return self._data

    def _lnstrecipe(self, node, params):
        if self._data == None:
            self._data = XmlData(node)
        else:
            msg = "Only a single <lnstrecipe> tag allowed in the document."
            raise RecipeError(msg, node)

        scheme = {"machines": self._machines,
                  "switches": self._switches,
                  "task": self._task}
        self._process_child_nodes(node, scheme)

    def _machines(self, node, params):
        if "machines" not in self._data:
            self._data["machines"] = XmlCollection(node)
        else:
            msg = "Only a single <machines> child allowed in <lnstrecipe>."
            raise RecipeError(msg, node)

        scheme = {"machine": self._machine}
        self._process_child_nodes(node, scheme)

    def _machine(self, node, params):
        subparser = MachineParse(self)
        m = subparser.parse(node)
        self._data["machines"].append(m)

    def _switches(self, node, params):
        if "switches" not in self._data:
            self._data["switches"] = XmlCollection(node)
        else:
            msg = "Only a single <switches> child allowed in <lnstrecipe>."
            raise RecipeError(msg, node)

        scheme = {"switch": self._switch}
        self._process_child_nodes(node, scheme)

    def _switch(self, node, params):
        subparser = MachineParse(self)
        s = subparser.parse(node)
        self._data["switches"].append(s)

    def _task(self, node, params):
        if "tasks" not in self._data:
            self._data["tasks"] = XmlCollection(node)

        subparser = TaskParse(self)
        task = subparser.parse(node)
        self._data["tasks"].append(task)

class MachineParse(LnstParser):
    def parse(self, node):
        self._data = XmlData(node)
        self._data["id"] = self._get_attribute(node, "id")

        scheme = {"params": self._params,
                  "interfaces": self._interfaces}
        self._process_child_nodes(node, scheme)

        return self._data

    def _params(self, node, params):
        if "params" in self._data:
            msg = "Only a single <params> child allowed under <machine>."
            raise RecipeError(msg, node)

        subparser = ParamsParse(self)
        self._data["params"] = subparser.parse(node)

    def _interfaces(self, node, params):
        if "interfaces" not in self._data:
            self._data["interfaces"] = XmlCollection(node)
        else:
            msg = "Only a single <interfaces> child allowed under <machine>."
            raise RecipeError(msg, node)

        scheme = {"eth": self._interface,
                  "bond": self._interface,
                  "team": self._interface,
                  "vlan": self._interface,
                  "macvlan": self._interface,
                  "bridge": self._interface}
        self._process_child_nodes(node, scheme)

    def _interface(self, node, params):
        subparser = InterfaceParse(self)
        iface = subparser.parse(node)
        self._data["interfaces"].append(iface)

class InterfaceParse(LnstParser):
    def parse(self, node):
        self._data = iface = XmlData(node)
        self._data["id"] = if_id = self._get_attribute(node, "id")

        iface["type"] = str(node.tagName)

        scheme = {"addresses": self._addresses}
        if iface["type"] in ["bond", "bridge", "vlan", "macvlan", "team"]:
            scheme["slaves"] = self._slaves
            scheme["options"] = self._options

            if self._has_attribute(node, "network"):
                msg = "Attribute network is not supported by type '%s' " + \
                      "interfaces" % iface["type"]
                raise RecipeError(msg, node)
        elif iface["type"] == "eth":
            iface["network"] = self._get_attribute(node, "network")

            scheme["params"] = self._params

        self._process_child_nodes(node, scheme)

        return iface

    def _params(self, node, params):
        if "params" in self._data:
            msg = "Only a single <params> child allowed under <%s>." \
                  % self._data["type"]
            raise RecipeError(msg, node)

        subparser = ParamsParse(self)
        self._data["params"] = subparser.parse(node)

    def _addresses(self, node, params):
        self._list_init(node, params, "addresses", {"address": self._address})

    def _address(self, node, params):
        if self._has_attribute(node, "value"):
            addr = self._get_attribute(node, "value")
        else:
            addr = self._get_text_content(node)

        self._data["addresses"].append(addr)

    def _options(self, node, params):
        self._list_init(node, params, "options", {"option": self._option})

    def _option(self, node, params):
        option = XmlData(node)
        option["name"] = self._get_attribute(node, "name")

        if self._has_attribute(node, "value"):
            option["value"] = self._get_attribute(node, "value")
        else:
            option["value"] = self._get_text_content(node)

        self._data["options"].append(option)

    def _slaves(self, node, params):
        self._list_init(node, params, "slaves", {"slave": self._slave})

    def _slave(self, node, params):
        slave = XmlData(node)
        if self._has_attribute(node, "id"):
            slave["id"] = self._get_attribute(node, "id")
        else:
            slave["id"] = self._get_text_content(node)

        scheme = {"options": self._slave_options}
        params = {"slave": slave}
        self._process_child_nodes(node, scheme, params)

        self._data["slaves"].append(slave)

    def _slave_options(self, node, params):
        if "options" not in params["slave"]:
            params["slave"]["options"] = XmlCollection(node)
        else:
            msg = "Only a single <options> child allowed under <slave>."
            raise RecipeError(msg, node)

        scheme = {"option": self._slave_option}
        self._process_child_nodes(node, scheme, params)

    def _slave_option(self, node, params):
        option = XmlData(node)
        option["name"] = self._get_attribute(node, "name")

        if self._has_attribute(node, "value"):
            option["value"] = self._get_attribute(node, "value")
        else:
            option["value"] = self._get_text_content(node)

        params["slave"]["options"].append(option)

    def _list_init(self, node, params, node_name, scheme):
        if node_name not in self._data:
            self._data[node_name] = XmlCollection(node)
        else:
            msg = "Only a single <%s> child allowed under <%s>." \
                  % (node_name, self._data["type"])
            raise RecipeError(msg, node)

        self._process_child_nodes(node, scheme, params)

class ParamsParse(LnstParser):
    def parse(self, node):
        self._data = XmlCollection(node)
        scheme = {"param": self._param}
        self._process_child_nodes(node, scheme)
        return self._data

    def _param(self, node, params):
        name = self._get_attribute(node, "name")

        if self._has_attribute(node, "value"):
            value = self._get_attribute(node, "value")
        else:
            value = self._get_text_content(node)

        param = XmlData(node)
        param["name"] = name
        param["value"] = value
        self._data.append(param)

class TaskParse(LnstParser):
    def parse(self, node):
        self._data = commands = XmlCollection(node)
        task = XmlData(node)
        task["commands"] = commands

        if self._has_attribute(node, "quit_on_fail"):
            task["quit_on_fail"] = self._get_attribute(node, "quit_on_fail")

        if self._has_attribute(node, "label"):
            task["label"] = self._get_attribute(node, "label")

        scheme = {"config": self._config,
                  "run": self._run,
                  "ctl_wait": self._ctl_wait,
                  "wait": self._wait,
                  "intr": self._intr,
                  "kill": self._kill}

        self._process_child_nodes(node, scheme)
        return task

    def _options(self, node, params):
        subparser = OptionsParse(self)
        opts = subparser.parse(node)
        params["cmd"]["options"] = opts

    def _config(self, node, params):
        cmd = XmlData(node)
        cmd["type"] = "config"
        cmd["machine"] = self._get_attribute(node, "machine")

        if self._has_attribute(node, "persistent"):
            cmd["persistent"] = self._get_attribute(node, "persistent")

        if self._has_attribute(node, "option"):
            cmd["options"] = XmlCollection(node)
            if self._has_attribute(node, "value"):
                opt = XmlData(node)
                opt["name"] = self._get_attribute(node, "option")
                opt["value"] = self._get_attribute(node, "value")

                cmd["options"] = XmlCollection(node)
                cmd["options"].append(opt)
            else:
                raise RecipeError("Missing option value.", cmd)
        else:
            params = {"cmd": cmd}
            scheme = {"options": self._options}
            self._process_child_nodes(node, scheme, params)

        self._data.append(cmd)

    def _run(self, node, params):
        cmd = XmlData(node)

        has_module = self._has_attribute(node, "module")
        has_command = self._has_attribute(node, "command")
        has_from = self._has_attribute(node, "from")

        if (has_module and has_command) or (has_module and has_from):
            msg = "Invalid combination of attributes."
            raise RecipeError(msg, cmd)

        if has_module:
            cmd["type"] = "test"
            cmd["module"] = self._get_attribute(node, "module")

            params = {"cmd": cmd}
            scheme = {"options": self._options}
            self._process_child_nodes(node, scheme, params)
        elif has_command:
            cmd["type"] = "exec"
            cmd["command"] = self._get_attribute(node, "command")

            if self._has_attribute(node, "from"):
                cmd["from"] = self._get_attribute(node, "from")

        cmd["machine"] = self._get_attribute(node, "machine")

        if self._has_attribute(node, "bg_id"):
            cmd["bg_id"] = self._get_attribute(node, "bg_id")

        if self._has_attribute(node, "timeout"):
            cmd["timeout"] = self._get_attribute(node, "timeout")

        if self._has_attribute(node, "expect"):
            cmd["expect"] = self._get_attribute(node, "expect")

        self._data.append(cmd)

    def _ctl_wait(self, node, param):
        cmd = XmlData(node)
        cmd["type"] = "ctl_wait"
        cmd["seconds"] = self._get_attribute(node, "seconds")
        self._data.append(cmd)

    def _signal_cmd(self, node, signal_name):
        cmd = XmlData(node)
        cmd["type"] = signal_name
        cmd["machine"] = self._get_attribute(node, "machine")
        cmd["bg_id"] = self._get_attribute(node, "bg_id")
        self._data.append(cmd)
        return cmd

    def _intr(self, node, param):
        self._signal_cmd(node, "intr")

    def _kill(self, node, param):
        self._signal_cmd(node, "kill")

    def _wait(self, node, param):
        self._signal_cmd(node, "wait")

class OptionsParse(LnstParser):
    def parse(self, node):
        self._data = opts = XmlCollection(node)

        scheme = {"option": self._option}
        self._process_child_nodes(node, scheme)

        return self._data

    def _option(self, node, params):
        option = XmlData(node)
        option["name"] = self._get_attribute(node, "name")
        option["value"] = self._get_attribute(node, "value")

        self._data.append(option)
