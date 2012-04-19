"""
This module defines NetTestParse class useful to parse xml recipes

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

from xml.dom.minidom import parseString
import logging
import os
import re
from NetConfig.NetConfigParse import NetConfigParse
from NetTest.NetTestCommand import str_command

def load_file(filename):
    handle = open(filename, "r")
    data = handle.read()
    handle.close()
    return data

class WrongCommandSequenceException(Exception):
    pass

class WrongIncludeSource(Exception):
    pass

class NetTestParse:
    def __init__(self, recipe_path):
        recipe_path = os.path.expanduser(recipe_path)
        self._recipe_xml_string = load_file(recipe_path)
        self._dirpath = os.path.dirname(recipe_path)
        self._recipe = None

    def _get_referenced_xml_path(self, filename):
        return os.path.join(self._dirpath, os.path.expanduser(filename))

    def _parse_machine(self, dom_machine):
        machine = {}

        dom_netmachineconfig = dom_machine.getElementsByTagName("netmachineconfig")[0]
        netmachineconfig_xml = dom_netmachineconfig.toxml()

        dom_netconfig = dom_machine.getElementsByTagName("netconfig")[0]
        netconfig_xml = dom_netconfig.toxml()

        ncparse = NetConfigParse(netmachineconfig_xml)
        machine["info"] = ncparse.get_machine_info()
        machine["netmachineconfig_xml"] = netmachineconfig_xml
        machine["netconfig_xml"] = netconfig_xml
        return machine

    def _parse_machines(self, dom_machines_grp):
        machines = {}
        for dom_machines_item in dom_machines_grp:
            dom_machines = dom_machines_item.getElementsByTagName("machine")
            for dom_machine in dom_machines:
                machine_id = int(dom_machine.getAttribute("id"))
                machines[machine_id] = self._parse_machine(dom_machine)
        return machines

    def _parse_definitions(self, dom_definitions_grp):
        definitions = {}
        for dom_definitions_item in dom_definitions_grp:
            dom_aliases = dom_definitions_item.getElementsByTagName("alias")
            for dom_alias in dom_aliases:
                alias_name = str(dom_alias.getAttribute("name"))
                alias_value = str(dom_alias.getAttribute("value"))
                definitions[alias_name] = alias_value
        return definitions

    def parse_recipe(self):
        recipe = {}
        dom = parseString(self._recipe_xml_string)

        self._load_included_parts(dom)
        dom_nettestrecipe = dom.getElementsByTagName("nettestrecipe")[0]

        dom_definitions_grp = dom_nettestrecipe.getElementsByTagName("define")
        self._definitions = self._parse_definitions(dom_definitions_grp)
        for define_tag in dom_definitions_grp:
            parent = define_tag.parentNode
            parent.removeChild(define_tag)

        dom_machines_grp = dom_nettestrecipe.getElementsByTagName("machines")
        self._expand_group(dom_machines_grp)
        recipe["machines"] = self._parse_machines(dom_machines_grp)

        dom_switches_grp = dom_nettestrecipe.getElementsByTagName("switches")
        self._expand_group(dom_switches_grp)
        recipe["switches"] = self._parse_machines(dom_switches_grp)

        self._recipe = recipe
        self._dom_nettestrecipe = dom_nettestrecipe

    def get_recipe(self):
        return self._recipe

    def _load_included_parts(self, dom_node):
        if dom_node.nodeType == dom_node.ELEMENT_NODE:
            source = str(dom_node.getAttribute("source"))
            if source:
                file_path = self._get_referenced_xml_path(source)
                xml_data = load_file(file_path)

                dom = parseString(xml_data)
                loaded_node = None
                try:
                    loaded_node = dom.getElementsByTagName(dom_node.nodeName)[0]
                except Exception:
                    err = ("No '%s' node present in included file '%s'."
                                        % (dom_node.nodeName, file_path))
                    raise WrongIncludeSource(err)

                parent = dom_node.parentNode
                parent.replaceChild(loaded_node, dom_node)
                self._load_included_parts(loaded_node)
                return

        for child in dom_node.childNodes:
            self._load_included_parts(child)

    def _recipe_eval(self, eval_data):
        try:
            return str(eval("self._recipe%s" % eval_data))
        except (KeyError, IndexError):
            print self._recipe
            logging.error("Wrong recipe_eval value \"%s\" passed"
                                      % eval_data)
            raise Exception

    def _parse_command_option(self, dom_option, options):
        logging.debug("Parsing command option")
        option_type = str(dom_option.getAttribute("type"))
        orig_value = None
        if not option_type:
            name = str(dom_option.getAttribute("name"))
            value = str(dom_option.getAttribute("value"))
        elif option_type == "recipe_eval":
            name = str(dom_option.getAttribute("name"))
            orig_value = str(dom_option.getAttribute("value"))
            value = str(self._recipe_eval(orig_value))
        else:
            logging.error("Unknown option type \"%s\"" % option_type)
            raise Exception("Unknown option type")

        logging.debug("Command option name \"%s\", value \"%s\""
                                        % (name, value))
        option = {"value": value}
        if option_type:
            option["type"] = option_type
        if orig_value:
            option["orig_value"] = orig_value
        if not name in options:
            options[name] = []
        options[name].append(option)

    def _parse_command(self, dom_command):
        logging.debug("Parsing command")
        recipe = self._recipe
        tmp = dom_command.getAttribute("machine_id")
        if tmp:
            machine_id = int(tmp)
            if machine_id and not machine_id in recipe["machines"]:
                logging.error("Invalid machine id")
                raise Exception("Invalid machine id")
        else:
            machine_id = 0 # controller id
        cmd_type = str(dom_command.getAttribute("type"))
        value = str(dom_command.getAttribute("value"))

        command = {"type": cmd_type, "value": value, "machine_id": machine_id}
        tmp = dom_command.getAttribute("timeout")
        if tmp:
            command["timeout"] = int(tmp)
        tmp = dom_command.getAttribute("bg_id")
        if tmp:
            command["bg_id"] = int(tmp)
        tmp = dom_command.getAttribute("desc")
        if tmp:
            command["desc"] = str(tmp)
        logging.debug("Parsed command: [%s]" % str_command(command))

        dom_options_grp = dom_command.getElementsByTagName("options")
        options = {}
        for dom_options_item in dom_options_grp:
            dom_options = dom_options_item.getElementsByTagName("option")
            for dom_option in dom_options:
                self._parse_command_option(dom_option, options)
        if options:
            command["options"] = options
        return command

    def _check_sequence(self, sequence):
        err = False
        bg_ids = {}
        for i, command in enumerate(sequence):
            machine_id = command["machine_id"]
            if not machine_id in bg_ids:
                bg_ids[machine_id] = set()

            cmd_type = command["type"]
            if cmd_type in ["wait", "intr", "kill"]:
                bg_id = int(command["value"])
                if bg_id in bg_ids[machine_id]:
                    bg_ids[machine_id].remove(bg_id)
                else:
                    logging.error("Found command \"%s\" for bg_id \"%s\" on "
                              "machine \"%d\" which was not previously "
                              "defined" % (cmd_type, bg_id, machine_id))
                    err = True

            if "bg_id" in command:
                bg_id = command["bg_id"]
                if not bg_id in bg_ids[machine_id]:
                    bg_ids[machine_id].add(bg_id)
                else:
                    logging.error("Command \"%d\" uses bg_id \"%d\" on machine "
                              "\"%d\" which is already used"
                                            % (i, bg_id, machine_id))
                    err = True

        for machine_id in bg_ids:
            for bg_id in bg_ids[machine_id]:
                logging.error("bg_id \"%d\" on machine \"%d\" has no kill/wait "
                          "command to it" % (bg_id, machine_id))
                err= True
        if err:
            raise WrongCommandSequenceException

    def parse_recipe_command_sequence(self):
        sequence = []
        dom_sequences = self._dom_nettestrecipe.getElementsByTagName("command_sequence")
        self._expand_group(dom_sequences, recipe_eval=True)

        for dom_sequence in dom_sequences:
            dom_commands = dom_sequence.getElementsByTagName("command")
            for dom_command in dom_commands:
                sequence.append(self._parse_command(dom_command))

        self._check_sequence(sequence)
        self._recipe["sequence"] = sequence

    def _expand(self, node, recipe_eval=False):
        if node.nodeType == node.ELEMENT_NODE:
            i = 0
            num_attributes = node.attributes.length
            while(i < num_attributes):
                attr = node.attributes.item(i)
                attr.value = self._expand_string(attr.value, recipe_eval)
                i += 1
        elif node.nodeType == node.TEXT_NODE:
            node.data = self._expand_string(node.data, recipe_eval)

        for child in node.childNodes:
            self._expand(child, recipe_eval)

    def _expand_group(self, group, recipe_eval=False):
        for node in group:
            self._expand(node, recipe_eval)

    def _expand_string(self, string, recipe_eval):
        eval_re = "\{\$recipe([^\{\}]+)\}"
        alias_re = "\{\$([^\{\}]*)\}"
        while True:
            eval_match = re.search(eval_re, string)
            if eval_match:
                eval_string = eval_match.group(0)
                eval_data = eval_match.group(1)
                if recipe_eval:
                    string = string.replace(eval_string,
                                        self._recipe_eval(eval_data))
                    continue
                else:
                    err = ("Accessing $recipe allowed only from command sequence: %s"
                                                        % string)
                    raise KeyError(err)
            alias_match = re.search(alias_re, string)
            if alias_match:
                alias = alias_match.group(0)
                alias_name = alias_match.group(1)
                try:
                    string = string.replace(alias,
                                self._definitions[alias_name])
                    continue
                except KeyError, err:
                    raise Exception("Alias '%s' doesn't exist!" % str(err))


            if not (eval_match and alias_match):
                break

        return string
