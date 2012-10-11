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
from Common.XmlProcessing import RecipeParser
from Common.XmlProcessing import XmlDomTreeInit
from Common.XmlProcessing import XmlProcessingError
from Common.NetUtils import normalize_hwaddr
from Common.Utils import bool_it
from Common.RecipePath import RecipePath

class NetTestParse(RecipeParser):
    def __init__(self, recipe_filepath):
        super(NetTestParse, self).__init__()

        self._filepath = recipe_filepath
        self._rp = RecipePath(None, self._filepath)
        self._include_root = self._rp.get_root()

        self._recipe = {}
        self._template_proc.set_definitions({"recipe": self._recipe})

    def parse_recipe(self):
        dom_init = XmlDomTreeInit()
        rp = self._rp
        xml_dom = dom_init.parse_string(rp.to_str(), rp.abs_path())

        first_pass = FirstPass(self)
        first_pass.parse(xml_dom)

        try:
            self._trigger_event("provisioning_requirements_ready", {})
        except Exception as exc:
            raise XmlProcessingError(str(exc), xml_dom)

        # process machine requirements if used in the recipe before
        # proceeding to the second pass
        provisioning = self._recipe["provisioning"]

        dom_init = XmlDomTreeInit()
        for name, req in provisioning["setup_requirements"].iteritems():
            xml = provisioning["allocated_machines"][name]
            dom = dom_init.parse_string(xml, "pool_machine_config")

            # replace the original machinerequires with
            # the config recived from MachinePool
            original_node = req["dom_node_ref"]
            parent = original_node.parentNode
            replacement_node = dom.getElementsByTagName("machineconfig")[0]

            parent.replaceChild(replacement_node, original_node)

        second_pass = SecondPass(self)
        second_pass.parse(xml_dom)


class FirstPass(RecipeParser):
    """
    Purpose of the first pass through the recipe is to detect
    machine requirements for provisioning.

    The purpose is generic, but the first pass exist only to
    detect provisioning at the moment.
    """

    _has_machineconfigs = False
    _provisioned_setup = False

    def parse(self, node):
        self._recipe["provisioning"] = {}
        self._recipe["provisioning"]["setup_requirements"] = {}

        if node.nodeType == node.DOCUMENT_NODE:
            scheme = {"nettestrecipe": self._nettestrecipe}
            self._process_child_nodes(node, scheme,
                        default_handler=self._ignore_tag)
        else:
            raise XmlProcessingError("Passed object is not a XML document")

    def _nettestrecipe(self, node, params):
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

        scheme = {"machineconfig": self._machineconfig,
                  "machinerequires": self._machinerequires}
        self._process_child_nodes(node, scheme, params,
                    default_handler=self._ignore_tag)

    def _machineconfig(self, node, params):
        if self._provisioned_setup:
            msg = "Cannot mix provisioned and non-provisioned machines"
            raise XmlProcessingError(msg, node)

        self._has_machineconfigs = True

    def _machinerequires(self, node, params):
        if self._has_machineconfigs:
            msg = "Cannot mix provisioned and non-provisioned machines"
            raise XmlProcessingError(msg, node)

        self._provisioned_setup = True

        machine_req = self._recipe["provisioning"]["setup_requirements"]
        m_id = params["id"]
        template = {}
        template["info"] = {}
        template["netdevices"] = {}
        machine_req[m_id] = template

        subparser = MachineRequiresParse(self)
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
            scheme = {"nettestrecipe": self._nettestrecipe}
            self._process_child_nodes(xml_dom, scheme)
        else:
            raise XmlProcessingError("Passed object is not a XML document")

    def _nettestrecipe(self, node, params):
        scheme = {"machines": self._machines,
                  "switches": self._switches,
                  "command_sequence": self._command_sequence}
        self._process_child_nodes(node, scheme)

    def _machines(self, node, params):
        self._recipe["machines"] = {}
        scheme = {"machine": self._machine}
        self._process_child_nodes(node, scheme)

    def _machine(self, node, params):
        subparser = MachineParse(self)
        subparser.set_type("host")
        subparser.parse(node)

    def _switches(self, node, params):
        self._recipe["switches"] = {}
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
        self._machine = {}
        self._recipe[self._target][self._id] = self._machine

        self._machine["info"] = {}
        self._machine["netdevices"] = {}
        self._machine["netconfig"] = {}

        scheme = {"machineconfig": self._machineconfig,
                  "netconfig": self._netconfig }
        self._process_child_nodes(node, scheme)

    def _machineconfig(self, node, params):
        subparser = MachineConfigParse(self)
        subparser.set_machine(self._id, self._machine)
        subparser.parse(node)

    def _netconfig(self, node, params):
        subparser = NetConfigParse(self)
        subparser.set_machine(self._id, self._machine)
        subparser.parse(node)

class MachineRequiresParse(RecipeParser):
    _requirements = None

    def set_template(self, tmp_dict):
        self._requirements = tmp_dict

    def parse(self, node):
        self._requirements["dom_node_ref"] = node

        scheme = {"info": self._info,
                  "netdevices": self._netdevices}
        self._process_child_nodes(node, scheme)

    def _info(self, node, params):
        template = self._requirements
        info = template["info"]

        if self._has_attribute(node, "hostname"):
            info["hostname"] = self._get_attribute(node, "hostname")

        if self._has_attribute(node, "libvirt_domain"):
            info["libvirt_domain"] = self._get_attribute(node,
                                                "libvirt_domain")

    def _netdevices(self, node, params):
        scheme = {"netdevice": self._netdevice}
        self._process_child_nodes(node, scheme)

    def _netdevice(self, node, params):
        template = self._requirements
        phys_id = self._get_attribute(node, "phys_id")

        dev = template["netdevices"][phys_id] = {}
        dev["network"] = self._get_attribute(node, "network")

        if self._has_attribute(node, "type"):
            dev["type"] = self._get_attribute(node, "type")

        if self._has_attribute(node, "hwaddr"):
            hwaddr = self._get_attribute(node, "hwaddr")
            dev["hwaddr"] = normalize_hwaddr(hwaddr)


class MachineConfigParse(RecipeParser):
    _machine_id = None
    _machine = None

    def set_machine(self, machine_id, machine):
        self._machine_id = machine_id
        self._machine = machine

    def parse(self, node):
        scheme = {"info": self._info,
                  "netdevices": self._netdevices}
        self._process_child_nodes(node, scheme)

    def _info(self, node, params):
        machine = self._machine
        info = machine["info"]

        info["hostname"] = self._get_attribute(node, "hostname")

        if self._has_attribute(node, "libvirt_domain"):
            info["libvirt_domain"] = self._get_attribute(node,
                                                "libvirt_domain")

        if self._has_attribute(node, "rootpass"):
            info["rootpass"] = self._get_attribute(node, "rootpass")

        if self._has_attribute(node, "rpcport"):
            info["rpcport"] = self._get_attribute(node, "rpcport", int)

        info["system_config"] = {}

        try:
            self._trigger_event("machine_info_ready",
                    {"machine_id": self._machine_id})
        except Exception as exc:
            raise XmlProcessingError(str(exc), node)

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
        dev["type"] = self._get_attribute(node, "type")
        dev["network"] = self._get_attribute(node, "network")

        # hwaddr attribute is optional for dynamic devices,
        # but it is required by non-dynamic devices
        if dev["create"] == None or self._has_attribute(node, "hwaddr"):
            hwaddr = self._get_attribute(node, "hwaddr")
            dev["hwaddr"] = normalize_hwaddr(hwaddr)

        # name attribute is only valid when the device is not dynamic
        if dev["create"] == None and self._has_attribute(node, "name"):
            dev["name"] = self._get_attribute(node, "name")

        # bridge attribute is valid only when the device is dynamic
        if dev["create"] == "libvirt" and \
           self._has_attribute(node, "libvirt_bridge"):
            dev["libvirt_bridge"] = self._get_attribute(node, "libvirt_bridge")

        try:
            self._trigger_event("netdevice_ready",
                    {"machine_id": self._machine_id, "dev_id": phys_id})
        except Exception as exc:
            raise XmlProcessingError(str(exc), node)


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
            raise XmlProcessingError(msg, node)

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
            if machine_id and not machine_id in recipe["machines"]:
                raise XmlProcessingError("Invalid machine_id", node)
        else:
            machine_id = "0" # controller id

        command["machine_id"] = machine_id
        command["type"]  = self._get_attribute(node, "type")

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
