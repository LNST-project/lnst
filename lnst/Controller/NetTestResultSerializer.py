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

from xml.dom.minidom import getDOMImplementation
from lnst.Common.NetTestCommand import str_command

def serialize_obj(obj, dom, el, upper_name="unnamed"):
    if isinstance(obj, dict):
        for key in obj:
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

class NetTestResultSerializer:
    def __init__(self):
        impl = getDOMImplementation()
        self._dom = impl.createDocument(None, "results", None)
        self._top_el = self._dom.documentElement
        self._cur_recipe_el = None

    def __str__(self):
        return self._dom.toprettyxml()

    def add_recipe(self, name):
        recipe_el = self._dom.createElement("recipe")
        recipe_el.setAttribute("name", name)
        self._top_el.appendChild(recipe_el)
        self._cur_recipe_el = recipe_el

    def add_cmd_result(self, command, cmd_res):
        command_el = self._dom.createElement("command")
        self._cur_recipe_el.appendChild(command_el)

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
