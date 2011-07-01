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
from NetConfig.NetConfigParse import NetConfigParse
from NetTest.NetTestCommand import str_command

def load_file(filename):
    handle = open(filename, "r")
    data = handle.read()
    handle.close()
    return data

class WrongCommandSequenceException(Exception):
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
        dom_netconfig = dom_machine.getElementsByTagName("netconfig")[0]

        source = str(dom_netmachineconfig.getAttribute("source"))
        if source:
            file_path = self._get_referenced_xml_path(source)
            netmachineconfig_xml = load_file(file_path)
        else:
            netmachineconfig_xml = dom_netmachineconfig.toxml()

        source = str(dom_netconfig.getAttribute("source"))
        if source:
            file_path = self._get_referenced_xml_path(source)
            netconfig_xml = load_file(file_path)
        else:
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

    def parse_recipe(self):
        recipe = {}
        dom = parseString(self._recipe_xml_string)
        dom_nettestrecipe = dom.getElementsByTagName("nettestrecipe")[0]

        dom_machines_grp = dom_nettestrecipe.getElementsByTagName("machines")
        recipe["machines"] = self._parse_machines(dom_machines_grp)

        dom_switches_grp = dom_nettestrecipe.getElementsByTagName("switches")
        recipe["switches"] = self._parse_machines(dom_switches_grp)

        self._recipe = recipe
        self._dom_nettestrecipe = dom_nettestrecipe

    def get_recipe(self):
        return self._recipe

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
            try:
                value = str(eval("self._recipe%s" % orig_value))
            except (KeyError, IndexError):
                logging.error("Wrong recipe_eval value \"%s\" passed"
                                    % orig_value)
                raise Exception
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
        for dom_sequence in dom_sequences:
            source = str(dom_sequence.getAttribute("source"))
            if source:
                """
                If source attribute is present, load sequence command
                from referenced xml file.
                """
                file_path = self._get_referenced_xml_path(source)
                xml_data = load_file(file_path)
                dom = parseString(xml_data)
                dom_sequence = dom.getElementsByTagName("command_sequence")[0]

            dom_commands = dom_sequence.getElementsByTagName("command")
            for dom_command in dom_commands:
                sequence.append(self._parse_command(dom_command))

        self._check_sequence(sequence)
        self._recipe["sequence"] = sequence
