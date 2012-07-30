#!/usr/bin/env python
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

def convert_recipe(file_path):
    dom = parse(file_path)

    change_netdev_to_iface(dom)
    remove_recipe_eval(dom)

    output = dom.toxml()
    output = re.sub(r"<\?xml[^>]*\?>", "", output)

    writer = open(file_path, "w")
    writer.write(output)
    writer.close()

def usage():
    print "Usage: %s recipe1 recipe2 dir1 ..." % sys.argv[0]

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
                        print "Converting %s" % full_path
                        convert_recipe(full_path)
        else:
            print "Converting %s" % file_path
            convert_recipe(file_path)
    return 0

if __name__ == "__main__":
    rv = main()
    sys.exit(rv)
