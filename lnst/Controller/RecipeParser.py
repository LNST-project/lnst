"""
This module defines RecipeParser class useful to parse xml recipes

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
import sys
from lxml import etree
from lnst.Common.Config import lnst_config
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.Utils import bool_it
from lnst.Common.RecipePath import RecipePath
from lnst.Controller.XmlParser import XmlParser
from lnst.Controller.XmlProcessing import XmlProcessingError, XmlData
from lnst.Controller.XmlProcessing import XmlCollection
from lnst.Controller.XmlTemplates import XmlTemplates, XmlTemplateError

class RecipeError(XmlProcessingError):
    pass

class RecipeParser(XmlParser):
    def __init__(self, recipe_path):
        recipe_path = RecipePath(None, recipe_path).abs_path()
        super(RecipeParser, self).__init__("schema-recipe.rng", recipe_path)

    def _process(self, lnst_recipe):
        recipe = XmlData(lnst_recipe)

        # machines
        machines_tag = lnst_recipe.find("network")
        if machines_tag is not None:
            machines = recipe["machines"] = XmlCollection(machines_tag)
            for machine_tag in machines_tag:
                machines.append(self._process_machine(machine_tag))

        # tasks
        tasks = recipe["tasks"] = XmlCollection()
        task_tags = lnst_recipe.findall("task")
        for task_tag in task_tags:
            tasks.append(self._process_task(task_tag))

        return recipe

    def _process_machine(self, machine_tag):
        machine = XmlData(machine_tag)
        machine["id"] = self._get_attribute(machine_tag, "id")

        # params
        params_tag = machine_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            machine["params"] = params

        # interfaces
        interfaces_tag = machine_tag.find("interfaces")
        if interfaces_tag is not None and len(interfaces_tag) > 0:
            machine["interfaces"] = XmlCollection(interfaces_tag)
            for interface_tag in interfaces_tag:
                interface = self._process_interface(interface_tag)
                machine["interfaces"].append(interface)

        return machine

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
        iface["type"] = iface_tag.tag

        # params
        params_tag = iface_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            iface["params"] = params

        # addresses
        addresses_tag = iface_tag.find("addresses")
        if addresses_tag is not None and len(addresses_tag) > 0:
            iface["addresses"] = XmlCollection(addresses_tag)
            for addr_tag in addresses_tag:
                if self._has_attribute(addr_tag, "value"):
                    addr = self._get_attribute(addr_tag, "value")
                else:
                    addr = self._get_content(addr_tag)
                iface["addresses"].append(addr)

        if iface["type"] == "eth":
            iface["network"] = self._get_attribute(iface_tag, "label")
        elif iface["type"] in ["bond", "bridge", "vlan", "macvlan", "team"]:
            # slaves
            slaves_tag = iface_tag.find("slaves")
            if slaves_tag is not None and len(slaves_tag) > 0:
                iface["slaves"] = XmlCollection(slaves_tag)
                for slave_tag in slaves_tag:
                    slave = XmlData(slave_tag)
                    slave["id"] = self._get_attribute(slave_tag, "id")

                    # slave options
                    opts_tag = slave_tag.find("options")
                    opts = self._proces_options(opts_tag)
                    if len(opts) > 0:
                        slave["options"] = opts

                    iface["slaves"].append(slave)

            # interface options
            opts_tag = iface_tag.find("options")
            opts = self._proces_options(opts_tag)
            if len(opts) > 0:
                iface["options"] = opts
        elif iface["type"] == "ovs_bridge":
            slaves_tag = iface_tag.find("slaves")
            iface["slaves"] = XmlCollection(slaves_tag)
            ovsb_slaves = []

            iface["ovs_conf"] = XmlData(slaves_tag)
            for slave_tag in slaves_tag:
                slave = XmlData(slave_tag)
                slave["id"] = str(self._get_attribute(slave_tag, "id"))
                ovsb_slaves.append(slave["id"])

                iface["slaves"].append(slave)

            vlan_elems = iface_tag.findall("vlan")
            vlans = iface["ovs_conf"]["vlans"] = XmlData(slaves_tag)
            for vlan in vlan_elems:
                vlan_tag = str(self._get_attribute(vlan, "tag"))
                if vlan_tag in vlans:
                    msg = "VLAN '%s' already defined for "\
                          "this ovs_bridge." % vlan_tag
                    raise RecipeError(msg, vlan)

                vlans[vlan_tag] = XmlData(vlan)
                vlans[vlan_tag]["slaves"] = XmlCollection(vlan)
                vlan_slaves = vlans[vlan_tag]["slaves"]

                slaves_tag = vlan.find("slaves")
                for slave_tag in slaves_tag:
                    slave_id = str(self._get_attribute(slave_tag, "id"))
                    if slave_id not in ovsb_slaves:
                        msg = "No port with id '%s' defined for "\
                              "this ovs_bridge." % slave_id
                        raise RecipeError(msg, slave_tag)

                    if slave_id in vlan_slaves:
                        msg = "Port '%s' already a member of vlan %s"\
                              % (slave_id, vlan_tag)
                        raise RecipeError(msg, slave_tag)
                    else:
                        vlan_slaves.append(slave_id)

            bonded_slaves = {}
            bond_elems = iface_tag.findall("bond")
            bonds = iface["ovs_conf"]["bonds"] = XmlData(slaves_tag)
            for bond_tag in bond_elems:
                bond_id = str(self._get_attribute(bond_tag, "id"))
                if bond_id in bonds:
                    msg = "Bond with id '%s' already defined for "\
                          "this ovs_bridge." % bond_id
                    raise RecipeError(msg, bond_tag)
                bonds[bond_id] = XmlData(bond_tag)
                bond_slaves = bonds[bond_id]["slaves"] = XmlCollection(bond_tag)

                slaves_tag = bond_tag.find("slaves")
                for slave_tag in slaves_tag:
                    slave_id = str(self._get_attribute(slave_tag, "id"))
                    if slave_id not in ovsb_slaves:
                        msg = "No port with id '%s' defined for "\
                              "this ovs_bridge." % slave_id
                        raise RecipeError(msg, slave_tag)

                    if slave_id in bonded_slaves:
                        msg = "Port with id '%s' already in bond with id '%s'"\
                              % (slave_id, bonded_slaves[slave_id])
                        raise RecipeError(msg, slave_tag)
                    else:
                        bonded_slaves[slave_id] = bond_id

                    bond_slaves.append(slave_id)

        return iface

    def _proces_options(self, opts_tag):
        options = XmlCollection(opts_tag)
        if opts_tag is not None:
            for opt_tag in opts_tag:
                opt = XmlData(opt_tag)
                opt["name"] = self._get_attribute(opt_tag, "name")
                if self._has_attribute(opt_tag, "value"):
                    opt["value"] = self._get_attribute(opt_tag, "value")
                else:
                    opt["value"] = self._get_content(opt_tag)
                options.append(opt)

        return options

    def _process_task(self, task_tag):
        task = XmlData(task_tag)

        if self._has_attribute(task_tag, "quit_on_fail"):
            task["quit_on_fail"] = self._get_attribute(task_tag, "quit_on_fail")

        if self._has_attribute(task_tag, "module_dir"):
            base_dir = os.path.dirname(task_tag.attrib["__file"])
            dir_path = str(self._get_attribute(task_tag, "module_dir"))
            exp_path = os.path.expanduser(dir_path)
            abs_path = os.path.join(base_dir, exp_path)
            norm_path = os.path.normpath(abs_path)
            task["module_dir"] = norm_path

        if self._has_attribute(task_tag, "tools_dir"):
            base_dir = os.path.dirname(task_tag.attrib["__file"])
            dir_path = str(self._get_attribute(task_tag, "tools_dir"))
            exp_path = os.path.expanduser(dir_path)
            abs_path = os.path.join(base_dir, exp_path)
            norm_path = os.path.normpath(abs_path)
            task["tools_dir"] = norm_path

        if self._has_attribute(task_tag, "python"):
            task["python"] = self._get_attribute(task_tag, "python")
            return task

        if len(task_tag) > 0:
            task["commands"] = XmlCollection(task_tag)
            for cmd_tag in task_tag:
                if cmd_tag.tag == "run":
                    cmd = self._process_run_cmd(cmd_tag)
                elif cmd_tag.tag == "config":
                    cmd = self._process_config_cmd(cmd_tag)
                elif cmd_tag.tag == "ctl_wait":
                    cmd = self._process_ctl_wait_cmd(cmd_tag)
                elif cmd_tag.tag in ["wait", "intr", "kill"]:
                    cmd = self._process_signal_cmd(cmd_tag)
                else:
                    msg = "Unknown command '%s'." % cmd_tag.tag
                    raise RecipeError(msg, cmd_tag)

                task["commands"].append(cmd)

        return task

    def _process_run_cmd(self, cmd_tag):
        cmd = XmlData(cmd_tag)
        cmd["host"] = self._get_attribute(cmd_tag, "host")

        has_module = self._has_attribute(cmd_tag, "module")
        has_command = self._has_attribute(cmd_tag, "command")
        has_from = self._has_attribute(cmd_tag, "from")

        if (has_module and has_command) or (has_module and has_from):
            msg = "Invalid combination of attributes."
            raise RecipeError(msg, cmd)

        if has_module:
            cmd["type"] = "test"
            cmd["module"] = self._get_attribute(cmd_tag, "module")

            # options
            opts_tag = cmd_tag.find("options")
            opts = self._proces_options(opts_tag)
            if len(opts) > 0:
                cmd["options"] = opts
        elif has_command:
            cmd["type"] = "exec"
            cmd["command"] = self._get_attribute(cmd_tag, "command")

            if self._has_attribute(cmd_tag, "from"):
                cmd["from"] = self._get_attribute(cmd_tag, "from")

        if self._has_attribute(cmd_tag, "bg_id"):
            cmd["bg_id"] = self._get_attribute(cmd_tag, "bg_id")

        if self._has_attribute(cmd_tag, "timeout"):
            cmd["timeout"] = self._get_attribute(cmd_tag, "timeout")

        if self._has_attribute(cmd_tag, "expect"):
            cmd["expect"] = self._get_attribute(cmd_tag, "expect")

        return cmd

    def _process_config_cmd(self, cmd_tag):
        cmd = XmlData(cmd_tag)
        cmd["type"] = "config"
        cmd["host"] = self._get_attribute(cmd_tag, "host")

        if self._has_attribute(cmd_tag, "persistent"):
            cmd["persistent"] = self._get_attribute(cmd_tag, "persistent")

        # inline option
        if self._has_attribute(cmd_tag, "option"):
            cmd["options"] = XmlCollection(cmd_tag)
            if self._has_attribute(cmd_tag, "value"):
                opt = XmlData(cmd_tag)
                opt["name"] = self._get_attribute(cmd_tag, "option")
                opt["value"] = self._get_attribute(cmd_tag, "value")

                cmd["options"] = XmlCollection(cmd_tag)
                cmd["options"].append(opt)
            else:
                raise RecipeError("Missing option value.", cmd)
        else:
            # options
            opts_tag = cmd_tag.find("options")
            opts = self._proces_options(opts_tag)
            if len(opts) > 0:
                cmd["options"] = opts

        return cmd

    def _process_ctl_wait_cmd(self, cmd_tag):
        cmd = XmlData(cmd_tag)
        cmd["type"] = "ctl_wait"
        cmd["seconds"] = self._get_attribute(cmd_tag, "seconds")
        return cmd

    def _process_signal_cmd(self, cmd_tag):
        cmd = XmlData(cmd_tag)
        cmd["type"] = cmd_tag.tag
        cmd["host"] = self._get_attribute(cmd_tag, "host")
        cmd["bg_id"] = self._get_attribute(cmd_tag, "bg_id")
        return cmd
