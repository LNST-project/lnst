#! /usr/bin/env python

# LNST Smoke Tests
# Author:  Ondrej Lichtner <olichtne@redhat.com>
# License: GNU GPLv2
# Based on generate-recipes.sh from Radek Pazdera <rpazdera@redhat.com>

# This script will generate a set of recipes for assessing the very basic
# functionality of LNST.

import os
import shutil
import re
import ConfigParser
import xml.dom.minidom

def print_test_usage():
    print ""

    print "To run these recipes, you need to have a pool prepared with at"
    print "least two machines. Both of them must have at least two test"
    print "interfaces connected to the same network segment."

    print ""

    print "   +-----------+          +--------+          +-----------+"
    print "   |           |----------|        |----------|           |"
    print "   |  Machine  |          | Switch |          |  Machine  |"
    print "   |     1     |----------|        |----------|     2     |"
    print "   |           |          +--------+          |           |"
    print "   +-----------+                              +-----------+"

    print "\nYou can execute the set using the following command:"
    print "    ./lnst-ctl -d recipes/smoke/tests/ run"

def replace_variables(recipe, name1, name2, variables):
    vars = dict(variables.items("defaults"))

    if variables.has_section("%s-%s" % (name1, name2)):
        section = variables.items("%s-%s" % (name1, name2))
        for name, val in section:
            vars[name] = val

    for name, val in vars.iteritems():
        recipe = recipe.replace("#%s#" % name, val)
    return recipe

def handleNode(node):
    if node.nodeType == node.ELEMENT_NODE:
        if node.hasAttribute("source"):
            src_file_name = node.getAttribute("source")
            loaded_dom = xml.dom.minidom.parse(src_file_name)
            loaded_node = None
            try:
                loaded_node = loaded_dom.getElementsByTagName(node.nodeName)[0]
            except Exception:
                msg = ("No '%s' element present in included file '%s'."
                                    % (node.nodeName, src_file_name))
                raise Exception(msg, node)

            old_attrs = node.attributes

            parent = node.parentNode
            parent.replaceChild(loaded_node, node)
            node = loaded_node

            # copy all of the original attributes to the sourced node
            for i in range(old_attrs.length):
                attr = old_attrs.item(i)
                # do not overwrite sourced attributes
                if not node.hasAttribute(attr.name) and attr.name != "source":
                    node.setAttribute(attr.name, attr.value)

            handleNode(node)
        else:
            childNodes = list(node.childNodes)
            for child in childNodes:
                if child.nodeType == node.TEXT_NODE and child.data.isspace():
                    node.removeChild(child)
                else:
                    handleNode(child)

def expand_sources(recipe):
    document = xml.dom.minidom.parseString(recipe)
    for child in document.childNodes:
        handleNode(child)
    recipe = document.toprettyxml()
    return recipe

def main():
    DIR = "tests/"
    LIB = "../lib/"
    vars_filename = "%svariables.conf" % LIB

    print "[LNST Smoke Tests]"
    print "Creating '%s' directory for the recipes..." % DIR,
    shutil.rmtree(DIR, ignore_errors=True)
    os.mkdir(DIR)
    os.chdir(DIR)
    print "[DONE]"

    sequences = ""
    for seq in os.listdir(LIB):
        if not re.match("seq-.*", seq):
            continue
        print "Found command sequence %s%s" % (LIB, seq)
        sequences += "\n    <command_sequence source=\"%s%s\"/>" % (LIB, seq)

    conf_files = [LIB+i for i in os.listdir(LIB) if re.match("conf-.*", i)]
    for conf in conf_files:
        print "Found configuration %s" % conf

    template_file = open("%s/recipe-temp.xml" % LIB, 'r')
    template = template_file.read()

    variables = ConfigParser.ConfigParser()
    variables.read(vars_filename)

    for machine1 in conf_files:
        for machine2 in conf_files:
            name1 = re.match(".*conf-(.*)\.xml", machine1).group(1)
            name2 = re.match(".*conf-(.*)\.xml", machine2).group(1)
            recipe_name = "recipe-%s-%s.xml" % (name1, name2)
            print "Generating %s%s..." % (DIR, recipe_name),

            recipe = template.replace("#CONF1#", machine1)\
                             .replace("#CONF2#", machine2)\
                             .replace("#SEQUENCES#", sequences)

            recipe = expand_sources(recipe)

            recipe = replace_variables(recipe, name1, name2, variables)

            recipe_file = open("%s" % recipe_name, 'w')
            recipe_file.write(recipe)
            recipe_file.close()

            print "[DONE]"

    print_test_usage()

if __name__ == "__main__":
    main()
