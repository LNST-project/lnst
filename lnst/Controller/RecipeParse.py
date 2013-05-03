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
from lnst.Common.XmlProcessing import LnstParser
from lnst.Common.XmlProcessing import XmlDomTreeInit
from lnst.Common.XmlProcessing import XmlProcessingError
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.Utils import bool_it
from lnst.Common.RecipePath import RecipePath

class RecipeParse(LnstParser):
    def __init__(self, recipe_filepath):
        super(RecipeParse, self).__init__()

        self._filepath = recipe_filepath
        self._rp = RecipePath(None, self._filepath)
        self._include_root = self._rp.get_root()

    def parse_recipe(self):
        dom_init = XmlDomTreeInit()
        rp = self._rp
        xml_dom = dom_init.parse_string(rp.to_str(), rp.abs_path())

        first_pass = FirstPass(self)
        first_pass.parse(xml_dom)

        self._trigger_event("provisioning_requirements_ready", {})

        second_pass = SecondPass(self)
        second_pass.parse(xml_dom)


class FirstPass(LnstParser):
    """
    Purpose of the first pass through the recipe is to detect
    machine requirements for provisioning.

    The purpose is generic, but the first pass exist only to
    detect provisioning at the moment.
    """

    def parse(self, node):
        if node.nodeType == node.DOCUMENT_NODE:
            scheme = {"lnstrecipe": self._lnstrecipe}
            self._process_child_nodes(node, scheme,
                        default_handler=self._ignore_tag)
        else:
            raise XmlProcessingError("Passed object is not a XML document")

    def _lnstrecipe(self, node, params):
        scheme = {"machines": self._machines}
        self._process_child_nodes(node, scheme,
                    default_handler=self._ignore_tag)

    def _machines(self, node, params):
        if not "machines" in self._data:
            self._data["machines"] = {}

        scheme = {"machine": self._machine}
        self._process_child_nodes(node, scheme,
                    default_handler=self._ignore_tag)

    def _machine(self, node, params):
        m_id = self._get_attribute(node, "id")
        if not m_id in self._data["machines"]:
            self._data["machines"][m_id] = {}

        if not "params" in self._data["machines"][m_id]:
            self._data["machines"][m_id]["params"] = {}

        if not "interfaces" in self._data["machines"][m_id]:
            self._data["machines"][m_id]["interfaces"] = {}

        target = self._data["machines"][m_id]["params"]
        params = {"id": m_id, "target": target}
        scheme = {"params": self._params,
                  "interfaces": self._interfaces}
        self._process_child_nodes(node, scheme, params,
                    default_handler=self._ignore_tag)

    def _params(self, node, params):
        subparser = ParamsParse(self)
        subparser.set_params_dict(params["target"])
        subparser.parse(node)

    def _interfaces(self, node, params):
        params = {"id": params["id"]}
        scheme = {"eth": self._interface,
                  "bond": self._interface,
                  "team": self._interface,
                  "vlan": self._interface,
                  "macvlan": self._interface,
                  "bridge": self._interface}
        self._process_child_nodes(node, scheme, params)

    def _interface(self, node, params):
        m_id = params["id"]
        machine = self._data["machines"][m_id]

        if_id = self._get_attribute(node, "id")
        if_type = node.tagName

        if if_id in machine["interfaces"]:
            msg = "Two interfaces with the same id '%s', " % if_id
            raise XmlProcessingError(msg)

        # Matching works with eth devices only
        if if_type != "eth":
            return

        if not if_id in machine["interfaces"]:
            machine["interfaces"][if_id] = {}
        iface = machine["interfaces"][if_id]

        iface["type"] = if_type
        iface["network"] = self._get_attribute(node, "network")

        if not "params" in machine["interfaces"][if_id]:
            machine["interfaces"][if_id]["params"] = {}

        target = machine["interfaces"][if_id]["params"]
        params = {"target": target}
        scheme = {"params": self._params}
        self._process_child_nodes(node, scheme, params,
                                  default_handler=self._ignore_tag)

    def _ignore_tag(self, node, params):
        pass


class SecondPass(LnstParser):
    """
    Second pass makes sure all recognized values from the recipe
    are properly saved into the self._data.

    This is where the real parsing is done.
    """

    def parse(self, xml_dom):
        if xml_dom.nodeType == xml_dom.DOCUMENT_NODE:
            scheme = {"lnstrecipe": self._lnstrecipe}
            self._process_child_nodes(xml_dom, scheme)
        else:
            raise XmlProcessingError("Passed object is not a XML document")

    def _lnstrecipe(self, node, params):
        scheme = {"machines": self._machines,
                  "switches": self._switches,
                  "command_sequence": self._command_sequence}
        self._process_child_nodes(node, scheme)

    def _machines(self, node, params):
        scheme = {"machine": self._machine}
        self._process_child_nodes(node, scheme)

    def _machine(self, node, params):
        subparser = MachineParse(self)
        subparser.set_type("host")
        subparser.parse(node)

    def _switches(self, node, params):
        scheme = {"switch": self._switch}
        self._process_child_nodes(node, scheme)

    def _switch(self, node, params):
        subparser = MachineParse(self)
        subparser.set_type("switch")
        subparser.parse(node)

    def _command_sequence(self, node, params):
        if not "sequences" in self._data:
            self._data["sequences"] = []

        subparser = CommandSequenceParse(self)
        subparser.parse(node)


class MachineParse(LnstParser):
    _target = "machines"

    def set_type(self, machine_type):
        if machine_type == "host":
            self._target = "machines"
        elif machine_type == "switch":
            self._target = "switches"
        else:
            raise XmlProcessingError("Unknown machine type")

    def parse(self, node):
        self._id = self._get_attribute(node, "id")

        recipe = self._data
        self._machine = recipe["machines"][self._id]
        self._machine["netconfig"] = {}

        scheme = {"params": self._ignore_tag,
                  "interfaces": self._interfaces}
        self._process_child_nodes(node, scheme)

    def _interfaces(self, node, params):
        scheme = {"eth": self._interface,
                  "bond": self._interface,
                  "team": self._interface,
                  "vlan": self._interface,
                  "macvlan": self._interface,
                  "bridge": self._interface}
        self._process_child_nodes(node, scheme)

    def _interface(self, node, params):
        subparser = InterfaceParse(self)
        subparser.set_machine(self._id, self._machine)
        subparser.parse(node)

    def _ignore_tag(self, node, params):
        pass

class InterfaceParse(LnstParser):
    _machine_id = None
    _machine = None
    _iface = None

    def set_machine(self, machine_id, machine):
        self._machine_id = machine_id
        self._machine = machine

    def parse(self, node):
        if_id = self._get_attribute(node, "id")

        if not if_id in self._machine["interfaces"]:
            self._machine["interfaces"][if_id] = {}
        self._iface = iface = self._machine["interfaces"][if_id]

        iface["type"] = node.tagName

        scheme = {"addresses": self._addresses}
        if iface["type"] in ["bond", "bridge", "vlan", "macvlan", "team"]:
            scheme["slaves"] = self._slaves
            scheme["options"] = self._options

            if self._has_attribute(node, "network"):
                msg = "Attribute network is not supported by type '%s' " + \
                      "interfaces" % iface["type"]
                raise XmlProcessingError(msg)
        elif iface["type"] == "eth":
            iface["network"] = self._get_attribute(node, "network")

            scheme["params"] = self._ignore_tag

        self._process_child_nodes(node, scheme)

        try:
            event_params = {"machine_id": self._machine_id, "if_id": if_id}
            self._trigger_event("interface_config_ready", event_params)
        except Exception as exc:
            msg = "Unable to configure interface %s on machine %s [%s]." % \
                    (if_id, self._machine_id, str(exc))
            logging.error(XmlProcessingError(str(msg), node))
            raise

    def _addresses(self, node, params):
        self._list_init(node, params, "addresses", {"address": self._address})

    def _address(self, node, params):
        if self._has_attribute(node, "value"):
            addr = self._get_attribute(node, "value")
        else:
            addr = self._get_text_content(node)

        self._iface["addresses"].append(addr)

    def _options(self, node, params):
        self._list_init(node, params, "options", {"option": self._option})

    def _option(self, node, params):
        name = self._get_attribute(node, "name")

        if self._has_attribute(node, "value"):
            value = self._get_attribute(node, "value")
        else:
            value = self._get_text_content(node)

        self._iface["options"].append((name, value))

    def _slaves(self, node, params):
        self._list_init(node, params, "slaves", {"slave": self._slave})

    def _slave(self, node, params):
        if self._has_attribute(node, "id"):
            slave_id = self._get_attribute(node, "id")
        else:
            slave_id = self._get_text_content(node)

        self._iface["slaves"].append(slave_id)

    def _list_init(self, node, params, node_name, scheme):
        self._iface[node_name] = []

        self._process_child_nodes(node, scheme, params)

    def _ignore_tag(self, node, params):
        pass

class ParamsParse(LnstParser):
    _params = None

    def set_params_dict(self, target):
        self._params = target

    def parse(self, node):
        scheme = {"param": self._param}
        self._process_child_nodes(node, scheme)

    def _param(self, node, params):
        name = self._get_attribute(node, "name")

        if self._has_attribute(node, "value"):
            value = self._get_attribute(node, "value")
        else:
            value = self._get_text_content(node)

        self._params[name] = value

class CommandSequenceParse(LnstParser):
    def parse(self, node):
        sequences = self._data["sequences"]
        sequences.append({})
        seq_num = len(sequences) - 1
        sequences[seq_num]["commands"] = []

        self._seq_num = seq_num
        self._seq_node = node

        if self._has_attribute(node, "quit_on_fail"):
            quit_on_fail = self._get_attribute(node, "quit_on_fail")
            sequences[seq_num]["quit_on_fail"] = quit_on_fail
        else:
            sequences[seq_num]["quit_on_fail"] = "no"

        scheme = {"command": self._command}
        self._process_child_nodes(node, scheme)

        self._check_sequence(sequences[seq_num])

    def _command(self, node, params):
        subparser = CommandParse(self)
        subparser.set_seq_num(self._seq_num)
        subparser.parse(node)

    def _check_sequence(self, sequence):
        err = False
        bg_ids = {}
        for i, command in enumerate(sequence["commands"]):
            machine_id = command["machine_id"]
            if not machine_id in bg_ids:
                bg_ids[machine_id] = set()

            cmd_type = command["type"]
            if cmd_type in ["wait", "intr", "kill"]:
                bg_id = command["value"]
                if bg_id in bg_ids[machine_id]:
                    bg_ids[machine_id].remove(bg_id)
                else:
                    logging.error("Found command \"%s\" for bg_id \"%s\" on "
                              "machine \"%s\" which was not previously "
                              "defined", cmd_type, bg_id, machine_id)
                    err = True

            if "bg_id" in command:
                bg_id = command["bg_id"]
                if not bg_id in bg_ids[machine_id]:
                    bg_ids[machine_id].add(bg_id)
                else:
                    logging.error("Command \"%d\" uses bg_id \"%s\" on machine "
                              "\"%s\" which is already used",
                                            i, bg_id, machine_id)
                    err = True

        for machine_id in bg_ids:
            for bg_id in bg_ids[machine_id]:
                logging.error("bg_id \"%s\" on machine \"%s\" has no kill/wait "
                          "command to it", bg_id, machine_id)
                err = True
        if err:
            msg = "Incorrect command sequence"
            raise XmlProcessingError(msg, self._seq_node)


class CommandParse(LnstParser):
    _seq_num = None
    _cmd_num = None

    def set_seq_num(self, num):
        self._seq_num = num

    def parse(self, node):
        recipe = self._data
        command = {}
        recipe["sequences"][self._seq_num]["commands"].append(command)
        self._cmd_num = len(recipe["sequences"][self._seq_num]["commands"]) - 1

        if self._has_attribute(node, "machine_id"):
            machine_id = self._get_attribute(node, "machine_id")
        else:
            machine_id = None

        if machine_id and machine_id not in recipe["machines"]:
            raise XmlProcessingError("Invalid machine_id", node)

        command["machine_id"] = machine_id
        command["type"]  = self._get_attribute(node, "type")

        if (command["type"] != "ctl_wait" and not machine_id) or\
           (machine_id and machine_id not in recipe["machines"]):
            raise XmlProcessingError("Invalid machine_id", node)

        command["value"] = None
        if self._has_attribute(node, "value"):
            command["value"] = self._get_attribute(node, "value")

        if self._has_attribute(node, "timeout"):
            command["timeout"] = self._get_attribute(node, "timeout", int)

        if self._has_attribute(node, "bg_id"):
            command["bg_id"] = self._get_attribute(node, "bg_id")

        if self._has_attribute(node, "desc"):
            command["desc"] = self._get_attribute(node, "desc")

        if command["type"] == "system_config":
            if self._has_attribute(node, "option"):
                command["option"] = self._get_attribute(node, "option")

            if self._has_attribute(node, "persistent"):
                command["persistent"] = self._get_attribute(node, "persistent",
                                                            bool_it)
            else:
                command["persistent"] = False
        elif command["type"] == "exec":
            if self._has_attribute(node, "from"):
                command["from"] = self._get_attribute(node, "from")
        elif command["type"] == "ctl_wait":
            if command["machine_id"] != None:
                msg = "Invalid attribute machine_id for command ctl_wait"
                raise XmlProcessingError(msg, node)

            try:
                command["value"] = int(command["value"])
            except ValueError:
                msg = "Invalid value for command ctl_wait"
                raise XmlProcessingError(msg, node)
            for key in command.keys():
                if key != "type" and key != "value" and\
                        key != "desc" and key != "machine_id":
                    msg = "Invalid attribute %s for command ctl_wait" % key
                    raise XmlProcessingError(msg, node)

        scheme = {"options": self._options}
        self._process_child_nodes(node, scheme)

    def _options(self, node, params):
        seq = self._seq_num
        cmd = self._cmd_num
        self._data["sequences"][seq]["commands"][cmd]["options"] = {}

        scheme = {"option": self._option}
        self._process_child_nodes(node, scheme)

    def _option(self, node, params):
        seq = self._seq_num
        cmd = self._cmd_num
        options = self._data["sequences"][seq]["commands"][cmd]["options"]

        name = self._get_attribute(node, "name")
        if not name in options:
            options[name] = []

        option = {}
        options[name].append(option)

        if self._has_attribute(node, "type"):
            opt_type = self._get_attribute(node, "type")
            option["type"] = opt_type
        else:
            opt_type = "default"

        if opt_type == "default":
            if self._has_attribute(node, "value"):
                value = self._get_attribute(node, "value")
            else:
                value = self._get_text_content(node)

            option["value"] = value
        else:
            msg = "Unknown option type \"%s\"" % opt_type
            raise XmlProcessingError(msg, node)
