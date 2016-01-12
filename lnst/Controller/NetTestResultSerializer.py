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
import datetime
from xml.dom.minidom import getDOMImplementation
from lnst.Common.Colours import decorate_with_preset
from lnst.Common.Config import lnst_config
from lxml import etree

def serialize_obj(obj, dom, el, upper_name="unnamed"):
    if isinstance(obj, dict):
        for key in obj:
            new_el = dom.createElement(key)
            if isinstance(obj[key], dict):
                new_el.setAttribute("type", "dict")
            elif isinstance(obj[key], list):
                new_el.setAttribute("type", "list")
            el.appendChild(new_el)
            serialize_obj(obj[key], dom, new_el, upper_name=key)
    elif isinstance(obj, list):
        for one in obj:
            new_el = dom.createElement("%s_item" % upper_name)
            if isinstance(one, dict):
                new_el.setAttribute("type", "dict")
            elif isinstance(one, list):
                new_el.setAttribute("type", "list")
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
        self._start_time = datetime.datetime.now()

    def add_recipe(self, name, match_num):
        recipe_result = {"name": name,
                         "result": "FAIL",
                         "tasks": [],
                         "pool_match": {},
                         "match_num": match_num}
        self._results.append(recipe_result)

    def set_recipe_pool_match(self, match):
        self._results[-1]["pool_match"] = match

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
            recipe_head = "%s match: %d" % (recipe["name"], recipe["match_num"])
            output_pairs.append((recipe_head, recipe["result"]))

            match = recipe["pool_match"]
            if match != {}:
                output_pairs.append((4*" " + "Pool match description:", ""))
                if "virtual" in match and match["virtual"]:
                    output_pairs.append((4*" " +\
                                         "Setup is using virtual machines.",
                                         ""))

                for m_id, m in match["machines"].iteritems():
                    output_pairs.append((4*" " + "host \"%s\" uses \"%s\"" %\
                                        (m_id, m["target"]), ""))
                    for if_id, pool_if in m["interfaces"].iteritems():
                        pool_id = pool_if["target"]
                        if "driver" in pool_if:
                            driver = pool_if["driver"]
                            output_pairs.append((6*" " + "interface \"%s\" "
                                                        "matched to \"%s\" "
                                                        "(driver: \"%s\")" %
                                                        (if_id, pool_id,
                                                            driver), ""))
                        else:
                            output_pairs.append((6*" " + "interface \"%s\" "
                                                        "matched to \"%s\" " %
                                                        (if_id, pool_id), ""))

            if recipe["result"] == "FAIL" and \
               "err_msg" in recipe and recipe["err_msg"] != "":
                err_msg = recipe["err_msg"]
                output_pairs.append((4*" " + "error message: " + err_msg, ""))

            seq_num = 1
            for task in recipe["tasks"]:
                output_pairs.append((4*" " + "task: %s" % seq_num,""))

                seq_num += 1

                m_id_max = 0
                for cmd, cmd_res in task:
                    if "host" in cmd and\
                        len(cmd["host"]) > m_id_max:
                            m_id_max = len(cmd["host"])
                for cmd, cmd_res in task:
                    self._format_command(cmd, cmd_res, output_pairs, m_id_max)

        self._print_pairs(output_pairs)

        current_time = datetime.datetime.now()
        dif_time = current_time - self._start_time
        days = dif_time.days
        hours = dif_time.seconds/3600
        minutes = dif_time.seconds/60 - hours*60
        seconds = dif_time.seconds - hours*3600 - minutes*60
        logging.info("Total test time: %d days, %d hours, %d minutes, "\
                     "%d seconds" % (days, hours, minutes, seconds))

    def _format_command(self, command, cmd_res, output_pairs, m_id_max):
        if cmd_res["passed"]:
            res = "PASS"
        else:
            res = "FAIL"

        if "host" in command:
            m_id = "host %s: " % command["host"]
            m_id += " " * (m_id_max - len(command["host"]))
        else:
            #len("ctl") == 3; len("host ") == 5; 5-3 = 2
            m_id = "ctl: " + " " * (m_id_max + 2)

        output_pairs.append((8*" " + m_id + cmd_res["res_header"], res))

        if "desc" in command and command["desc"] != None:
            output_pairs.append((12*" " + "description: " + command["desc"], ""))

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

    def _generate_xml(self):
        impl = getDOMImplementation()
        doc = impl.createDocument(None, "results", None)

        top_el = doc.documentElement

        for recipe in self._results:
            recipe_el = doc.createElement("recipe")
            recipe_el.setAttribute("name", recipe["name"])
            recipe_el.setAttribute("result", recipe["result"])
            recipe_el.setAttribute("match_num", str(recipe["match_num"]))

            top_el.appendChild(recipe_el)

            match = recipe["pool_match"]
            if match != {}:
                match_el = doc.createElement("pool_match")

                if "virtual" in match and match["virtual"]:
                    match_el.setAttribute("virtual", "true")
                else:
                    match_el.setAttribute("virtual", "false")

                for m_id, m in match["machines"].iteritems():
                    m_el = doc.createElement("m_match")
                    m_el.setAttribute("host_id", str(m_id))
                    m_el.setAttribute("pool_id", str(m["target"]))

                    for if_id, pool_id in m["interfaces"].iteritems():
                        if_el = doc.createElement("if_match")
                        if_el.setAttribute("if_id", str(if_id))
                        if_el.setAttribute("pool_if_id", str(pool_id))
                        m_el.appendChild(if_el)

                    match_el.appendChild(m_el)


                recipe_el.appendChild(match_el)

            if recipe["result"] == "FAIL" and \
               "err_msg" in recipe and recipe["err_msg"] != "":
                err_el = doc.createElement("error_message")
                err_text = doc.createTextNode(recipe["err_msg"])
                err_el.appendChild(err_text)
                recipe_el.appendChild(err_el)

            for task in recipe["tasks"]:
                cmd_seq_el = doc.createElement("task")
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
        return doc

    def get_result_xml(self):
        doc = self._generate_xml()
        return doc.toprettyxml()

    def get_result_html(self):
        xslt_url = lnst_config.get_option("environment", "xslt_url")
        xslt = etree.parse(xslt_url)

        xml = self._generate_xml().toprettyxml()
        etree_xml = etree.fromstring(xml)

        transform = etree.XSLT(xslt)

        transformed_xml = transform(etree_xml)
        return "<!DOCTYPE html>\n" + str(transformed_xml)
