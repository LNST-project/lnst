"""
This module defines NetTestResultSerializer class which serves for serializing
results of command sequence to XML

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
from xml.dom.minidom import getDOMImplementation
from lnst.Common.NetTestCommand import str_command
from lnst.Common.Colours import decorate_string, decorate_with_preset

def serialize_obj(obj, dom, el, upper_name="unnamed"):
    if isinstance(obj, dict):
        for key in obj:
            if upper_name == "options":
                new_el = dom.createElement("option")
                new_el.setAttribute("name", key)
            else:
                new_el = dom.createElement(key)
            el.appendChild(new_el)
            serialize_obj(obj[key], dom, new_el, upper_name=key)
    elif isinstance(obj, list):
        for one in obj:
            new_el = dom.createElement("%s_item" % upper_name)
            el.appendChild(new_el)
            serialize_obj(one, dom, new_el)
    else:
        text = dom.createTextNode(str(obj))
        el.appendChild(text)

def get_node_val(node):
    content = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            content.append(child.nodeValue)
    return str(''.join(content).strip())

class NetTestResultSerializer:
    def __init__(self):
        impl = getDOMImplementation()
        self._dom = impl.createDocument(None, "results", None)
        self._top_el = self._dom.documentElement
        self._cur_recipe_el = None
        self._cur_cmd_seq_el = None

    def __str__(self):
        return self._dom.toprettyxml()

    def add_recipe(self, name):
        recipe_el = self._dom.createElement("recipe")
        recipe_el.setAttribute("name", name)
        recipe_el.setAttribute("result", "FAIL")
        self._top_el.appendChild(recipe_el)
        self._cur_recipe_el = recipe_el
        self._cur_cmd_seq_el = None

    def set_recipe_result(self, result):
        if result and result["passed"]:
            self._cur_recipe_el.setAttribute("result", "PASS")
        else:
            self._cur_recipe_el.setAttribute("result", "FAIL")
            if "err_msg" in result:
                err_el = self._dom.createElement("error_message")
                err_text = self._dom.createTextNode(result["err_msg"])
                err_el.appendChild(err_text)
                self._cur_recipe_el.appendChild(err_el)

    def add_task(self):
        cmd_seq_el = self._dom.createElement("command_sequence")
        self._cur_recipe_el.appendChild(cmd_seq_el)
        self._cur_cmd_seq_el = cmd_seq_el

    def add_cmd_result(self, command, cmd_res):
        command_el = self._dom.createElement("command")
        self._cur_cmd_seq_el.appendChild(command_el)

        for key in command:
            if key == "options":
                continue
            command_el.setAttribute(key, str(command[key]))

        result_el = self._dom.createElement("result")
        command_el.appendChild(result_el)

        if cmd_res["passed"]:
            res = "PASS"
        else:
            res = "FAIL"
        result_el.setAttribute("result", res)

        if "err_msg" in cmd_res:
            err_el = self._dom.createElement("error_message")
            err_text = self._dom.createTextNode(cmd_res["err_msg"])
            err_el.appendChild(err_text)
            result_el.appendChild(err_el)

        if "res_data" in cmd_res:
            res_data_el = self._dom.createElement("result_data")
            serialize_obj(cmd_res["res_data"], self._dom, res_data_el)
            command_el.appendChild(res_data_el)

    def print_summary(self):
        output_pairs = []

        for recipe in self._top_el.getElementsByTagName("recipe"):
            recipe_name = recipe.getAttribute("name")
            recipe_res = recipe.getAttribute("result")
            output_pairs.append((recipe_name, recipe_res))

            if recipe_res == "FAIL":
                err_node = None
                for child in recipe.childNodes:
                    if child.nodeName == "error_message":
                        err_node = child
                        break
                if err_node:
                    text = get_node_val(err_node)
                    output_pairs.append((4*" "+"error message: "+text, ""))

            seq_num = 1
            for cmd_seq in recipe.getElementsByTagName("command_sequence"):
                command_sequence = 4*" "+"cmd_seq: %s" % seq_num
                output_pairs.append((command_sequence, ""))

                seq_num = seq_num + 1

                for command in cmd_seq.getElementsByTagName("command"):
                    self._format_command(command, output_pairs)

        self._print_pairs(output_pairs)

    def _format_command(self, command, output_pairs):
        cmd_type = command.getAttribute("type")
        if cmd_type == "test":
            self._format_test_command(command, output_pairs)
        elif cmd_type == "wait":
            self._format_wait_command(command, output_pairs)
        elif cmd_type == "intr":
            self._format_intr_command(command, output_pairs)
        elif cmd_type == "kill":
            self._format_kill_command(command, output_pairs)
        elif cmd_type == "ctl_wait":
            self._format_ctl_wait_command(command, output_pairs)
        elif cmd_type == "exec":
            self._format_exec_command(command, output_pairs)
        elif cmd_type == "config":
            self._format_config(command, output_pairs)

        result_node = command.getElementsByTagName("result")[0]
        cmd_res = result_node.getAttribute("result")

        if cmd_res == "FAIL":
            err_node = result_node.getElementsByTagName("error_message")
            if len(err_node) != 0:
                err_node = err_node[0]
                text = get_node_val(err_node)
                output_pairs.append((12*" "+"error message: "+text, ""))

    def _format_test_command(self, command, output_pairs):
        result_node = command.getElementsByTagName("result")[0]
        cmd_res = result_node.getAttribute("result")

        cmd_val = command.getAttribute("module")
        cmd_type = command.getAttribute("type")
        if command.hasAttribute("bg_id"):
            bg_id = " bg_id: %s" %  command.getAttribute("bg_id")
        else:
            bg_id = ""
        cmd = 8*" "+"%-14s%s%s" %(cmd_type, cmd_val, bg_id)
        output_pairs.append((cmd, cmd_res))

    def _format_wait_command(self, command, output_pairs):
        result_node = command.getElementsByTagName("result")[0]
        cmd_res = result_node.getAttribute("result")

        cmd_val = command.getAttribute("proc_id")
        cmd_type = command.getAttribute("type")
        if command.hasAttribute("bg_id"):
            bg_id = " bg_id: %s" %  command.getAttribute("bg_id")
        else:
            bg_id = ""
        cmd = 8*" "+"%-13s id: %s%s" %(cmd_type, cmd_val, bg_id)
        output_pairs.append((cmd, cmd_res))

    def _format_intr_command(self, command, output_pairs):
        self._format_wait_command(command, output_pairs)

    def _format_kill_command(self, command, output_pairs):
        self._format_wait_command(command, output_pairs)

    def _format_exec_command(self, command, output_pairs):
        result_node = command.getElementsByTagName("result")[0]
        cmd_res = result_node.getAttribute("result")

        cmd_val = command.getAttribute("command")
        cmd_type = command.getAttribute("type")
        if command.hasAttribute("bg_id"):
            bg_id = " bg_id: %s" %  command.getAttribute("bg_id")
        else:
            bg_id = ""
        cmd = 8*" "+"%-14s%s%s" %(cmd_type, cmd_val, bg_id)
        output_pairs.append((cmd, cmd_res))

    def _format_ctl_wait_command(self, command, output_pairs):
        result_node = command.getElementsByTagName("result")[0]
        cmd_res = result_node.getAttribute("result")

        cmd_val = command.getAttribute("seconds")
        cmd_type = command.getAttribute("type")
        cmd = 8*" "+"%-14s%ss" %(cmd_type, cmd_val)
        output_pairs.append((cmd, cmd_res))

    def _format_config(self, command, output_pairs):
        result_node = command.getElementsByTagName("result")[0]
        cmd_res = result_node.getAttribute("result")

        cmd_type = command.getAttribute("type")
        if command.hasAttribute("bg_id"):
            bg_id = " bg_id: %s" %  command.getAttribute("bg_id")
        else:
            bg_id = ""
        cmd = 8*" "+"%-14s%s" %(cmd_type, bg_id)
        output_pairs.append((cmd, cmd_res))

        result_data_nodes = command.getElementsByTagName("result_data")
        if len(result_data_nodes) != 0:
            result_data_node = result_data_nodes[0]
            options_nodes = result_data_node.getElementsByTagName("options")
            for options_node in options_nodes:
                for option in options_node.getElementsByTagName("options_item"):
                    previous_node = option.getElementsByTagName("previous_val")[0]
                    current_node = option.getElementsByTagName("current_val")[0]
                    name_node = option.getElementsByTagName("name")[0]
                    previous_val = get_node_val(previous_node)
                    current_val = get_node_val(current_node)
                    name = get_node_val(name_node)
                    opt_left = 12*" "+"%s" % name
                    opt_right = "previous: %s current: %s" \
                                % (previous_val, current_val)
                    output_pairs.append((opt_left, opt_right))

    def _print_pairs(self, output_pairs):
        max_left = 0
        max_right = 0
        for left, right in output_pairs:
            if len(left) > max_left and right != "":
                max_left = len(left)
            if len(right) > max_right:
                max_right = len(right)

        # +1 for the alignment of " PASS" or " FAIL"
        # +2 for spacing aroun the whole block
        full_length = max_left + max_right + 1 + 2

        if full_length % 2:
            full_length = full_length + 2
        else:
            full_length = full_length + 1

        header = " SUMMARY ".center(full_length, "=")
        coloured_summary = decorate_with_preset("SUMMARY", "highlight")
        logging.info(header.replace("SUMMARY", coloured_summary))

        for left, right in output_pairs:
            if right != "":
                space_fill = full_length - len(left) - len(right) - 1 - 2
                if right == "PASS":
                    right = decorate_with_preset(right, "pass")
                elif right == "FAIL":
                    right = decorate_with_preset(right, "fail")
                right = " %s" % right

                output = left + (space_fill)*" " + right
            else:
                output = left + " "
            logging.info(" %s " % output)
        logging.info("="*(full_length))
