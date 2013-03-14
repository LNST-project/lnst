"""
This module defines NetTestParse class useful to parse xml recipes

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
from lnst.Common.XmlProcessing import RecipeParser
from lnst.Common.XmlProcessing import XmlDomTreeInit
from lnst.Common.XmlProcessing import XmlProcessingError
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.Utils import bool_it
from lnst.Common.RecipePath import RecipePath

class NetTestParse(RecipeParser):
    def __init__(self, recipe_filepath):
        super(NetTestParse, self).__init__()

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


class FirstPass(RecipeParser):
    """
    Purpose of the first pass through the recipe is to detect
    machine requirements for provisioning.

    The purpose is generic, but the first pass exist only to
    detect provisioning at the moment.
    """

    def parse(self, node):
        self._recipe["provisioning"]["setup_requirements"] = {}

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
        scheme = {"machine": self._machine}
        self._process_child_nodes(node, scheme,
                    default_handler=self._ignore_tag)

    def _machine(self, node, params):
        params = {}
        params["id"] = self._get_attribute(node, "id")

        scheme = {"requirements": self._requirements}
        self._process_child_nodes(node, scheme, params,
                    default_handler=self._ignore_tag)

    def _requirements(self, node, params):
        machine_req = self._recipe["provisioning"]["setup_requirements"]
        m_id = params["id"]
        template = {}
        template["netdevices"] = {}
        machine_req[m_id] = template

        subparser = RequirementsParse(self)
        subparser.set_template(template)
        subparser.parse(node)

    def _ignore_tag(self, node, params):
        pass


class SecondPass(RecipeParser):
    """
    Second pass makes sure all recognized values from the recipe
    are properly saved into the self._recipe.

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
        if not "sequences" in self._recipe:
            self._recipe["sequences"] = []

        subparser = CommandSequenceParse(self)
        subparser.parse(node)


class MachineParse(RecipeParser):
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

        recipe = self._recipe
        self._machine = recipe["machines"][self._id]
        self._machine["netconfig"] = {}

        scheme = {"requirements": self._requirements,
                  "netconfig": self._netconfig }
        self._process_child_nodes(node, scheme)

    def _netconfig(self, node, params):
        subparser = NetConfigParse(self)
        subparser.set_machine(self._id, self._machine)
        subparser.parse(node)

    def _requirements(self, node, params):
        try:
            self._trigger_event("machine_ready", {"machine_id": self._id})
        except Exception as exc:
            logging.error(XmlProcessingError(str(exc), node))
            raise

class ParamsParse(RecipeParser):
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

class RequirementsParse(RecipeParser):
    _requirements = None

    def set_template(self, tmp_dict):
        self._requirements = tmp_dict

    def parse(self, node):
        self._requirements["params"] = {}
        self._requirements["netdevices"] = {}

        scheme = {"params": self._params,
                  "netdevices": self._netdevices}
        params = {"target": self._requirements["params"]}
        self._process_child_nodes(node, scheme, params)

    def _params(self, node, params):
        subparser = ParamsParse(self)
        subparser.set_params_dict(params["target"])
        subparser.parse(node)

    def _netdevices(self, node, params):
        scheme = {"netdevice": self._netdevice}
        self._process_child_nodes(node, scheme)

    def _netdevice(self, node, params):
        reqs = self._requirements
        phys_id = self._get_attribute(node, "phys_id")

        dev = reqs["netdevices"][phys_id] = {}
        dev["network"] = self._get_attribute(node, "network")

        dev["params"] = {}

        scheme = {"params": self._params}
        params = {"target": dev["params"]}
        self._process_child_nodes(node, scheme, params)

        if "type" in dev["params"]:
            dev["type"] = dev["params"]["type"]

        if "hwaddr" in dev["params"]:
            dev["hwaddr"] = normalize_hwaddr(dev["params"]["hwaddr"])


class SlaveMachineParse(RecipeParser):
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

class NetConfigParse(RecipeParser):
    _machine_id = None
    _machine = None

    def set_machine(self, machine_id, machine):
        self._machine_id = machine_id
        self._machine = machine

    def parse(self, node):
        netconfig = self._machine["netconfig"]
        self._netconfig = netconfig

        devices = self._machine["netdevices"]
        self._devices = devices

        scheme = {"interface": self._interface}
        self._process_child_nodes(node, scheme)

    def _interface(self, node, params):
        netconfig = self._netconfig
        devices = self._devices

        dev_id = self._get_attribute(node, "id")
        if not dev_id in netconfig:
            netconfig[dev_id] = {}
        else:
            msg = "Netdevice 'id' used more than once"
            raise XmlProcessingError(msg, node)

        dev = netconfig[dev_id]
        dev["type"] = self._get_attribute(node, "type")

        if self._has_attribute(node, "phys_id"):
            self._process_phys_id_attr(node, dev)

        params = {"dev_id": dev_id}
        scheme = {"addresses": self._addresses}
        scheme["options"] = self._options
        if dev["type"] == "eth":
            pass
        elif dev["type"] in ["bond", "bridge", "vlan", "macvlan", "team"]:
            scheme["slaves"] = self._slaves
        else:
            logging.warn("unknown type \"%s\"" % dev["type"])

        self._process_child_nodes(node, scheme, params)

        try:
            self._trigger_event("interface_config_ready",
                    {"machine_id": self._machine_id,
                     "netdev_config_id": dev_id})
        except Exception as exc:
            msg = "Unable to configure interface %s on machine %s [%s]." % \
                    (dev_id, self._machine_id, str(exc))
            logging.error(XmlProcessingError(str(msg), node))
            raise

    def _process_phys_id_attr(self, node, dev):
        netconfig = self._netconfig
        devices = self._devices

        if dev["type"] == "eth":
            phys_id = self._get_attribute(node, "phys_id")
            self._check_phys_id(node, phys_id, netconfig)
            dev["phys_id"] = phys_id

            if phys_id in devices:
                phys_dev = devices[phys_id]
                if phys_dev["type"] == dev["type"]:
                    dev["hwaddr"] = phys_dev["hwaddr"]
                    if "name" in phys_dev:
                        dev["name"] = phys_dev["name"]
            else:
                msg = "phys_id passed but does not match any device on machine"
                raise XmlProcessingError(msg, node)
        else:
            logging.warn("phys_id found on non-eth netdev, ignoring")


    @staticmethod
    def _check_phys_id(node, dev_pid, config):
        for key in config:
            if not "phys_id" in config[key]:
                continue
            if config[key]["phys_id"] == dev_pid:
                msg = "same phys_id \"%s\" used more than once" % dev_pid
                raise XmlProcessingError(msg, node)

    def _addresses(self, node, params):
        self._list_init(node, params, "addresses", {"address": self._address})

    def _address(self, node, params):
        if self._has_attribute(node, "value"):
            addr = self._get_attribute(node, "value")
        else:
            addr = self._get_text_content(node)

        dev_id = params["dev_id"]
        self._netconfig[dev_id]["addresses"].append(addr)

    def _options(self, node, params):
        self._list_init(node, params, "options", {"option": self._option})

    def _option(self, node, params):
        name = self._get_attribute(node, "name")

        if self._has_attribute(node, "value"):
            value = self._get_attribute(node, "value")
        else:
            value = self._get_text_content(node)

        dev_id = params["dev_id"]
        self._netconfig[dev_id]["options"].append((name, value))

    def _slaves(self, node, params):
        self._list_init(node, params, "slaves", {"slave": self._slave})

    def _slave(self, node, params):
        if self._has_attribute(node, "id"):
            slave_id = self._get_attribute(node, "id")
        else:
            slave_id = self._get_text_content(node)

        dev_id = params["dev_id"]
        self._netconfig[dev_id]["slaves"].append(slave_id)

    def _list_init(self, node, params, node_name, scheme):
        dev_id = params["dev_id"]
        dev = self._netconfig[dev_id]
        dev[node_name] = []

        self._process_child_nodes(node, scheme, params)


class CommandSequenceParse(RecipeParser):
    def parse(self, node):
        sequences = self._recipe["sequences"]
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


class CommandParse(RecipeParser):
    _seq_num = None
    _cmd_num = None

    def set_seq_num(self, num):
        self._seq_num = num

    def parse(self, node):
        recipe = self._recipe
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
        self._recipe["sequences"][seq]["commands"][cmd]["options"] = {}

        scheme = {"option": self._option}
        self._process_child_nodes(node, scheme)

    def _option(self, node, params):
        seq = self._seq_num
        cmd = self._cmd_num
        options = self._recipe["sequences"][seq]["commands"][cmd]["options"]

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
