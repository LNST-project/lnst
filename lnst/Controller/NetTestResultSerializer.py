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
        self._results = []

    def add_recipe(self, name):
        recipe_result = {"name": name,
                         "result": "FAIL",
                         "tasks": []}
        self._results.append(recipe_result)

    def set_recipe_result(self, result):
        if result and result["passed"]:
            self._results[-1]["result"] = "PASS"
        else:
            self._results[-1]["result"] = "FAIL"

            if "err_msg" in result:
                self._results[-1]["err_msg"] = result["err_msg"]

    def add_task(self):
        self._results[-1]["tasks"].append([])

    def add_cmd_result(self, command, cmd_res):
        self._results[-1]["tasks"][-1].append((command, cmd_res))

    def print_summary(self):
        output_pairs = []

        for recipe in self._results:
            output_pairs.append((recipe["name"], recipe["result"]))

            if recipe["result"] == "FAIL" and \
               "err_msg" in recipe and recipe["err_msg"] != "":
                err_msg = recipe["err_msg"]
                output_pairs.append((4*" " + "error message: " + err_msg, ""))

            seq_num = 1
            for task in recipe["tasks"]:
                output_pairs.append((4*" " + "task: %s" % seq_num,""))

                seq_num += 1

                for cmd, cmd_res in task:
                    self._format_command(cmd, cmd_res, output_pairs)

        self._print_pairs(output_pairs)

    def _format_command(self, command, cmd_res, output_pairs):
        if cmd_res["passed"]:
            res = "PASS"
        else:
            res = "FAIL"
        output_pairs.append((8*" " + cmd_res["res_header"], res))

        if "msg" in cmd_res and cmd_res["msg"] != "":
            output_pairs.append((12*" " + "message: " + cmd_res["msg"], ""))

        if "report" in cmd_res and cmd_res["report"] != "":
            for line in cmd_res["report"].splitlines():
                out = decorate_with_preset(line, "faded")
                output_pairs.append((12*" " + out, ""))

    def _print_pairs(self, output_pairs):
        max_left = 0
        max_right = 0
        for left, right in output_pairs:
            if len(left) > max_left:
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

    def get_result_xml(self):
        impl = getDOMImplementation()
        doc = impl.createDocument(None, "results", None)
        top_el = doc.documentElement

        for recipe in self._results:
            recipe_el = doc.createElement("recipe")
            recipe_el.setAttribute("name", recipe["name"])
            recipe_el.setAttribute("result", recipe["result"])

            top_el.appendChild(recipe_el)

            if recipe["result"] == "FAIL" and \
               "err_msg" in recipe and recipe["err_msg"] != "":
                err_el = doc.createElement("error_message")
                err_text = doc.createTextNode(recipe["err_msg"])
                err_el.appendChild(err_text)
                recipe_el.appendChild(err_el)

            for task in recipe["tasks"]:
                cmd_seq_el = doc.createElement("command_sequence")
                recipe_el.appendChild(cmd_seq_el)

                for cmd, cmd_res in task:
                    command_el = doc.createElement("command")
                    cmd_seq_el.appendChild(command_el)

                    for key in cmd:
                        if key == "options":
                            continue
                        command_el.setAttribute(key, str(cmd[key]))

                    result_el = doc.createElement("result")
                    command_el.appendChild(result_el)

                    if cmd_res["passed"]:
                        res = "PASS"
                    else:
                        res = "FAIL"
                    result_el.setAttribute("result", res)

                    if "msg" in cmd_res and cmd_res["msg"]:
                        msg_el = doc.createElement("message")
                        msg_text = doc.createTextNode(cmd_res["msg"])
                        msg_el.appendChild(msg_text)
                        result_el.appendChild(msg_el)

                    if "res_data" in cmd_res and cmd_res["res_data"]:
                        res_data_el = doc.createElement("result_data")
                        serialize_obj(cmd_res["res_data"], doc, res_data_el)
                        command_el.appendChild(res_data_el)
        return doc.toprettyxml()
