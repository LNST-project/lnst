"""
This module defines RecipeParser class useful to parse xml recipes

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import os
from lnst.Common.Path import Path
from lnst.Controller.XmlParser import XmlParser
from lnst.Controller.XmlProcessing import XmlProcessingError, XmlData
from lnst.Controller.XmlProcessing import XmlCollection

class RecipeError(XmlProcessingError):
    pass

class RecipeParser(XmlParser):
    def __init__(self, recipe_path):
        recipe_path = Path(None, recipe_path).abs_path()
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

            lo_netns = []
            unique_ids = []
            for interface_tag in interfaces_tag:
                interfaces = self._process_interface(interface_tag)

                for interface in interfaces:
                    if interface['id'] in unique_ids:
                        msg = "Interface with ID \"%s\" has already been "\
                              "defined for this machine." % interface['id']
                        raise RecipeError(msg, interface_tag)
                    else:
                        unique_ids.append(interface['id'])

                    if interface['type'] == 'lo':
                        if interface['netns'] in lo_netns:
                            msg = "Only one loopback device per netns "\
                                  "is allowed."
                            raise RecipeError(msg, interface_tag)
                        else:
                            lo_netns.append(interface['netns'])
                    elif interface['type'] == "ovs_bridge":
                        ovs_conf = interface["ovs_conf"]
                        for i in ovs_conf["tunnels"] + ovs_conf["internals"]:
                            if i['id'] in unique_ids:
                                msg = "Interface with ID \"%s\" has already "\
                                      "been defined for this machine." %\
                                      i['id']
                                raise RecipeError(msg, i)
                            else:
                                unique_ids.append(i['id'])

                machine["interfaces"].extend(interfaces)

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
        iface["type"] = iface_tag.tag

        if iface["type"] == "veth_pair":
            iface = self._process_interface(iface_tag[0])[0]
            iface2 = self._process_interface(iface_tag[1])[0]

            iface["peer"] = iface2["id"]
            iface2["peer"] = iface["id"]

            return [iface, iface2]

        iface["id"] = self._get_attribute(iface_tag, "id")

        iface["netns"] = None
        if self._has_attribute(iface_tag, "netns"):
            iface["netns"] = self._get_attribute(iface_tag, "netns")

        # netem
        netem_tag = iface_tag.find("netem")
        if netem_tag is not None:
            iface["netem"] = self._process_netem(netem_tag)

        # params
        params_tag = iface_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            iface["params"] = params

        # addresses
        addresses_tag = iface_tag.find("addresses")
        addrs = self._process_addresses(addresses_tag)
        iface["addresses"] = addrs

        if iface["type"] == "eth":
            iface["network"] = self._get_attribute(iface_tag, "label")
        elif iface["type"] in ["bond", "bridge", "macvlan", "team"]:
            # slaves
            slaves_tag = iface_tag.find("slaves")
            if slaves_tag is not None and len(slaves_tag) > 0:
                iface["slaves"] = XmlCollection(slaves_tag)
                for slave_tag in slaves_tag:
                    slave = XmlData(slave_tag)
                    slave["id"] = self._get_attribute(slave_tag, "id")

                    # slave options
                    opts_tag = slave_tag.find("options")
                    opts = self._process_options(opts_tag)
                    if len(opts) > 0:
                        slave["options"] = opts

                    iface["slaves"].append(slave)

            # interface options
            opts_tag = iface_tag.find("options")
            opts = self._process_options(opts_tag)
            if len(opts) > 0:
                iface["options"] = opts
        elif iface["type"] in ["vti", "vti6"]:
            # interface options
            opts_tag = iface_tag.find("options")
            opts = self._process_options(opts_tag)
            iface["options"] = opts
        elif iface["type"] in ["vlan"]:
            # real_dev of the VLAN interface
            slaves_tag = iface_tag.find("slaves")
            if slaves_tag is None or len(slaves_tag) != 1:
                msg = "VLAN '%s' need exactly one slave definition."\
                        % iface["id"]
                raise RecipeError(msg, iface_tag)

            iface["slaves"] = XmlCollection(slaves_tag)

            slave_tag = slaves_tag[0]
            slave = XmlData(slave_tag)
            slave["id"] = self._get_attribute(slave_tag, "id")

            iface["slaves"].append(slave)

            # interface options
            opts_tag = iface_tag.find("options")
            opts = self._process_options(opts_tag)
            if len(opts) > 0:
                iface["options"] = opts
        elif iface["type"] in ["vxlan", "gre", "ipip"]:
            # real_dev of the interface
            slaves_tag = iface_tag.find("slaves")
            if slaves_tag is not  None and len(slaves_tag) > 1:
                msg = "%s '%s' needs one or no slave definition."\
                        % (iface["type"], iface["id"])
                raise RecipeError(msg, iface_tag)

            if slaves_tag:
                iface["slaves"] = XmlCollection(slaves_tag)
                slave_tag = slaves_tag[0]
                slave = XmlData(slave_tag)
                slave["id"] = self._get_attribute(slave_tag, "id")
                iface["slaves"].append(slave)

            # interface options
            opts_tag = iface_tag.find("options")
            opts = self._process_options(opts_tag)
            if len(opts) > 0:
                iface["options"] = opts
        elif iface["type"] == "ovs_bridge":
            slaves_tag = iface_tag.find("slaves")
            iface["slaves"] = XmlCollection(slaves_tag)
            ovsb_slaves = []

            iface["ovs_conf"] = XmlData(slaves_tag)
            if slaves_tag is not None:
                for slave_tag in slaves_tag:
                    slave = XmlData(slave_tag)
                    slave["id"] = str(self._get_attribute(slave_tag, "id"))
                    ovsb_slaves.append(slave["id"])

                    opts_tag = slave_tag.find("options")
                    opts = self._process_options(opts_tag)
                    slave["options"] = opts

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

                opts_tag = bond_tag.find("options")
                opts = self._process_options(opts_tag)
                if len(opts) > 0:
                    bonds[bond_id]["options"] = opts

            unique_ids = []
            tunnels = iface["ovs_conf"]["tunnels"] = XmlCollection(slaves_tag)
            tunnel_elems = iface_tag.findall("tunnel")
            for tunnel_elem in tunnel_elems:
                tunnels.append(XmlData(tunnel_elem))
                tunnel = tunnels[-1]
                tunnel["id"] = str(self._get_attribute(tunnel_elem, "id"))
                if tunnel["id"] in unique_ids:
                    msg = "Tunnel with id '%s' already defined for "\
                          "this ovs_bridge." % tunnel["id"]
                    raise RecipeError(msg, tunnel_elem)
                else:
                    unique_ids.append(tunnel["id"])

                t = str(self._get_attribute(tunnel_elem, "type"))
                tunnel["type"] = t

                opts_elem = tunnel_elem.find("options")
                opts = self._process_options(opts_elem)
                if len(opts) > 0:
                    tunnel["options"] = opts

                # addresses
                addresses_tag = tunnel_elem.find("addresses")
                addrs = self._process_addresses(addresses_tag)
                tunnel["addresses"] = addrs

            iface["ovs_conf"]["internals"] = XmlCollection(slaves_tag)
            internals = iface["ovs_conf"]["internals"]
            internal_elems = iface_tag.findall("internal")
            for internal_elem in internal_elems:
                internals.append(XmlData(internal_elem))
                internal = internals[-1]
                internal["id"] = str(self._get_attribute(internal_elem, "id"))
                if internal["id"] in unique_ids:
                    msg = "Internal id '%s' already defined for "\
                          "this ovs_bridge." % internal["id"]
                    raise RecipeError(msg, internal_elem)
                else:
                    unique_ids.append(internal["id"])

                opts_elem = internal_elem.find("options")
                opts = self._process_options(opts_elem)
                if len(opts) > 0:
                    internal["options"] = opts

                # addresses
                addresses_tag = internal_elem.find("addresses")
                addrs = self._process_addresses(addresses_tag)
                internal["addresses"] = addrs

            iface["ovs_conf"]["flow_entries"] = XmlCollection(slaves_tag)
            flow_entries = iface["ovs_conf"]["flow_entries"]
            flow_elems = iface_tag.findall("flow_entries")
            if len(flow_elems) == 1:
                entries = flow_elems[0].findall("entry")
                for entry in entries:
                    if self._has_attribute(entry, "value"):
                        flow_entries.append(self._get_attribute(entry,
                                                                "value"))
                    else:
                        flow_entries.append(self._get_content(entry))

        return [iface]

    def _process_addresses(self, addresses_tag):
        addresses = XmlCollection(addresses_tag)
        if addresses_tag is not None and len(addresses_tag) > 0:
            for addr_tag in addresses_tag:
                if self._has_attribute(addr_tag, "value"):
                    addr = self._get_attribute(addr_tag, "value")
                else:
                    addr = self._get_content(addr_tag)
                addresses.append(addr)
        return addresses

    def _process_options(self, opts_tag):
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

    def _validate_netem(self, options, netem_op, netem_tag):
        if netem_op == "delay":
            valid = False
            jitter = False
            correlation = False
            distribution = False
            valid_distributions = ["normal", "uniform", "pareto", "paretonormal"]
            for opt in options:
                if "time" in opt.values():
                    valid = True
                elif "distribution" in opt.values():
                    if opt["value"] not in valid_distributions:
                        raise RecipeError("netem: invalid distribution type", netem_tag)
                    else:
                        distribution = True
                elif "jitter" in opt.values():
                    jitter =  True
                elif "correlation" in opt.values():
                    correlation = True
            if not jitter:
                if correlation or distribution:
                    raise RecipeError("netem: jitter option is mandatory when using <correlation> or <distribution>", netem_tag)
            if not valid:
                raise RecipeError("netem: time option is mandatory for <delay>", netem_tag)
        elif netem_op == "loss":
            for opt in options:
                if "percent" in opt.values():
                    return
            raise RecipeError("netem: percent option is mandatory for <loss>", netem_tag)
        elif netem_op == "duplication":
            for opt in options:
                if "percent" in opt.values():
                    return
            raise RecipeError("netem: percent option is mandatory for <duplication>", netem_tag)
        elif netem_op == "corrupt":
            for opt in options:
                if "percent" in opt.values():
                    return
            raise RecipeError("netem: percent option is mandatory for <corrupt>", netem_tag)
        elif netem_op == "reordering":
            for opt in options:
                if "percent" in opt.values():
                    return
            raise RecipeError("netem: percent option is mandatory for <reordering>", netem_tag)

    def _process_netem(self, netem_tag):
        interface = XmlData(netem_tag)
        # params
        for netem_op in ["delay", "loss", "duplication", "corrupt", "reordering"]:
            netem_op_tag = netem_tag.find(netem_op)
            if netem_op_tag is not None:
                options_tag = netem_op_tag.find("options")
                options = self._process_options(options_tag)
                if len(options) > 0:
                    self._validate_netem(options, netem_op, netem_tag)
                    interface[netem_op] = options
        return interface

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

        cmd["netns"] = None
        if self._has_attribute(cmd_tag, "netns"):
            cmd["netns"] = self._get_attribute(cmd_tag, "netns")

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
            opts = self._process_options(opts_tag)
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

        cmd["netns"] = None
        if self._has_attribute(cmd_tag, "netns"):
            cmd["netns"] = self._get_attribute(cmd_tag, "netns")

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
            opts = self._process_options(opts_tag)
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
        cmd["netns"] = None
        return cmd
