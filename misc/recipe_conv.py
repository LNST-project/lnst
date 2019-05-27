#!/usr/bin/env python3
"""
Recipe converter

This script will help you convert your old recipes with the
outdated conventions that are now unsupported in LNST.

You can pass a list of files or dirs to it and it will
remove all recipe-evals and change netdevices in netconfig
to interfaces.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import sys
import os
import re
from xml.dom.minidom import parse

def change_netdev_to_iface(dom):
    configs = dom.getElementsByTagName("netconfig")
    for config in configs:
        netdevs = config.getElementsByTagName("netdevice")
        for dev in netdevs:
            dev.tagName = "interface"

def remove_recipe_eval(dom):
    opts = dom.getElementsByTagName("option")
    for opt in opts:
        if opt.hasAttribute("type"):
            opt_type = opt.getAttribute("type")
            if opt_type == "recipe_eval":
                opt.removeAttribute("type")
                subscript = opt.getAttribute("value")
                opt.setAttribute("value", "{$recipe%s}" % subscript)

def _rename_attr(node, prev_name, new_name):
    if node.hasAttribute(prev_name):
        value = node.getAttribute(prev_name)
        node.removeAttribute(prev_name)
        node.setAttribute(new_name, value)

def cmd_seqs_to_tasks(dom):
    seqs = dom.getElementsByTagName("command_sequence")

    for seq in seqs:
        dom.renameNode(seq, "task", "task")

        cmds = seq.getElementsByTagName("command")
        for cmd in cmds:
            cmd_type = cmd.getAttribute("type")
            cmd.removeAttribute("type")

            dom.renameNode(cmd, cmd_type, cmd_type)

            if cmd.hasAttribute("machine_id"):
                _rename_attr(cmd, "machine_id", "machine")

            # Change 'pass_result' to expect
            if cmd.hasAttribute("pass_result"):
                value = cmd.getAttribute("pass_result")
                cmd.removeAttribute("pass_result")

                # In this case, the value must be converted as well
                value = "fail"
                if re.match(r"(?i)(true)", value) or \
                   re.match(r"(?i)(yes)", value) or value == "1":
                    value = "pass"
                cmd.setAttribute("expect", value)

            if cmd_type == "test":
                dom.renameNode(cmd, "run", "run")
                _rename_attr(cmd, "value", "module")
            elif cmd_type == "exec":
                dom.renameNode(cmd, "run", "run")
                _rename_attr(cmd, "value", "command")
            elif cmd_type == "system_config":
                dom.renameNode(cmd, "config", "config")
            elif cmd_type in ["wait", "intr", "kill"]:
                _rename_attr(cmd, "value", "bg_id")
            elif cmd_type == "ctl_wait":
                _rename_attr(cmd, "value", "seconds")

def convert_recipe(file_path):
    dom = parse(file_path)

    #change_netdev_to_iface(dom)
    #remove_recipe_eval(dom)
    cmd_seqs_to_tasks(dom)

    output = dom.toxml()
    output = re.sub(r"<\?xml[^>]*\?>", "", output)

    output = output.replace("&quot;", "\"")
    output = output.replace("&gt;", ">")
    output = output.replace("&lt;", "<")

    writer = open(file_path, "w")
    writer.write(output)
    writer.close()

def usage():
    print("Usage: %s recipe1 recipe2 dir1 ..." % sys.argv[0])

def main():
    if len(sys.argv) <= 1 or "-h" in sys.argv:
        usage()
        return 0

    files = sys.argv[1:]

    for file_path in files:
        if os.path.isdir(file_path):
            for root, dirs, file_names in os.walk(file_path):
                for file_name in file_names:
                    if re.match(r"^.*\.xml$", file_name):
                        full_path = "%s/%s" % (root, file_name)
                        full_path = os.path.normpath(full_path)
                        print("Converting %s" % full_path)
                        convert_recipe(full_path)
        else:
            print("Converting %s" % file_path)
            convert_recipe(file_path)
    return 0

if __name__ == "__main__":
    rv = main()
    sys.exit(rv)
