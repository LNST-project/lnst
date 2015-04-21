"""
This module contains code to aid processing templates in XML files/recipes
while they're being parsed.

Templates are strings enclosed in curly braces {} and can be present
in all text elements of the XML file (this includes tag values or
attribute values). Templates cannot be used as a stubstitution for tag
names, attribute names or any other structural elements of the document.

There are two supported types of templates:

    * aliases   - $alias_name
    * functions - function_name(param1, param2)

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import re
from lxml import etree
from lnst.Controller.XmlProcessing import XmlTemplateString
from lnst.Controller.Machine import MachineError, PrefixMissingError

class XmlTemplateError(Exception):
    pass

class TemplateFunc(object):
    def __init__(self, args, machines):
        self._check_args(args)
        self._args = args

        self._machines = machines

    def __str__(self):
        return self._implementation()

    def _check_args(self, args):
        pass

    def _implementation(self):
        pass

class IpFunc(TemplateFunc):
    def _check_args(self, args):
        if len(args) > 3:
            msg = "Function ip() takes at most 3 arguments, %d passed" \
                  % len(args)
            raise XmlTemplateError(msg)
        if len(args) < 2:
            msg = "Function ip() must have at least 2 arguments, %d passed" \
                  % len(args)
            raise XmlTemplateError(msg)

        if len(args) == 3:
            try:
                int(args[2])
            except ValueError:
                msg = "The third argument of ip() function must be an integer"
                raise XmlTemplateError(msg)

    def _implementation(self):
        m_id = self._args[0]
        if_id = self._args[1]
        addr = 0
        if len(self._args) == 3:
            addr = self._args[2]

        try:
            machine = self._machines[m_id]
        except KeyError:
            msg = "First parameter of function ip() is invalid: " \
                  "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)

        try:
            iface = machine.get_interface(if_id)
        except MachineError:
            msg = "Second parameter of function ip() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)

        try:
            return iface.get_address(int(addr))
        except IndexError:
            msg = "There is no address with index %s on machine %s, " \
                  "interface %s." % (addr, m_id, if_id)
            raise XmlTemplateError(msg)

class DevnameFunc(TemplateFunc):
    def _check_args(self, args):
        if len(args) != 2:
            msg = "Function devname() takes 2 arguments, %d passed." % len(args)
            raise XmlTemplateError(msg)

    def _implementation(self):
        m_id = self._args[0]
        if_id = self._args[1]

        try:
            machine = self._machines[m_id]
        except KeyError:
            msg = "First parameter of function devname() is invalid: " \
                  "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)

        try:
            iface = machine.get_interface(if_id)
        except MachineError:
            msg = "Second parameter of function devname() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)

        try:
            return iface.get_devname()
        except MachineError:
            msg = "Devname not availablefor interface '%s' on machine '%s'." \
                                                    % (m_id, if_id)
            raise XmlTemplateError(msg)

class PrefixFunc(TemplateFunc):
    def _check_args(self, args):
        if len(args) > 3:
            msg = "Function prefix() takes at most 3 arguments, %d passed" \
                  % len(args)
            raise XmlTemplateError(msg)
        if len(args) < 2:
            msg = "Function prefix() must have at least 2 arguments, %d " \
                  "passed" % len(args)
            raise XmlTemplateError(msg)

        if len(args) == 3:
            try:
                int(args[2])
            except ValueError:
                msg = "The third argument of prefix() function must be an " \
                      "integer"
                raise XmlTemplateError(msg)

    def _implementation(self):
        m_id = self._args[0]
        if_id = self._args[1]
        addr = 0
        if len(self._args) == 3:
            addr = self._args[2]

        try:
            machine = self._machines[m_id]
        except KeyError:
            msg = "First parameter of function prefix() is invalid: " \
                  "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)

        try:
            iface = machine.get_interface(if_id)
        except MachineError:
            msg = "Second parameter of function prefix() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)

        try:
            return iface.get_prefix(int(addr))
        except IndexError:
            msg = "There is no address with index %s on machine %s, " \
                  "interface %s." % (addr, m_id, if_id)
            raise XmlTemplateError(msg)
        except PrefixMissingError:
            msg = "Address with the index %s for the interface %s on machine" \
                  "%s does not contain any prefix" % (addr, m_id, if_id)

class HwaddrFunc(TemplateFunc):
    def _check_args(self, args):
        if len(args) != 2:
            msg = "Function hwaddr() takes 2 arguments, %d passed." % len(args)
            raise XmlTemplateError(msg)

    def _implementation(self):
        m_id = self._args[0]
        if_id = self._args[1]

        try:
            machine = self._machines[m_id]
        except KeyError:
            msg = "First parameter of function hwaddr() is invalid: " \
                  "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)

        try:
            iface = machine.get_interface(if_id)
        except MachineError:
            msg = "Second parameter of function hwaddr() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)

        try:
            return iface.get_hwaddr()
        except MachineError:
            msg = "Hwaddr not availablefor interface '%s' on machine '%s'." \
                                                    % (m_id, if_id)
            raise XmlTemplateError(msg)

class XmlTemplates:
    """ This class serves as template processor """

    _alias_re = "\{\$([a-zA-Z0-9_]+)\}"
    _func_re  = "\{([a-zA-Z0-9_]+)\(([^\(\)]*)\)\}"

    _func_map = {"ip": IpFunc, "hwaddr": HwaddrFunc, "devname": DevnameFunc, \
                 "prefix": PrefixFunc }

    def __init__(self, definitions=None):
        if definitions:
            self._definitions = [definitions]
        else:
            self._definitions = [{}]

        self._machines = {}
        self._reserved_aliases = []

    def set_definitions(self, defs):
        """ Set alias definitions

        All existing definitions and namespace levels are
        destroyed and replaced with new definitions.
        """
        del self._definitions
        self._definitions = [defs]

    def get_definitions(self):
        """ Return definitions dict

        Definitions are returned as a single dictionary of
        all currently defined aliases, regardless the internal
        division to namespace levels.
        """
        defs = {}
        for level in self._definitions:
            for name, val in level.iteritems():
                defs[name] = val

        return defs

    def set_machines(self, machines):
        """ Assign machine information

        XmlTemplates use these information about the machines
        to resolve template functions within the recipe.
        """
        self._machines = machines

    def set_aliases(self, defined, overriden):
        """ Set aliases defined or overriden from CLI """

        for name, value in defined.iteritems():
            self.define_alias(name, value)

        self._overriden_aliases = overriden

    def define_alias(self, name, value):
        """ Associate an alias name with some value

        The value can be of an atomic type or an array. The
        definition is added to the current namespace level.
        """

        if not name in self._reserved_aliases:
            self._definitions[-1][name] = value
        else:
            raise XmlTemplateError("Alias name '%s' is reserved" % name)

    def add_namespace_level(self):
        """ Create new namespace level

            This method will create a new level for definitions on
            the stack. All aliases, that will be defined after this
            call will be dropped as soon as `drop_namespace_level'
            is called.
        """
        self._definitions.append({})

    def drop_namespace_level(self):
        """ Remove one namespace level

            This method will erease all defined aliases since the
            last call of `add_namespace_level' method. All aliases,
            that were defined beforehand will be kept.
        """
        self._definitions.pop()

    def _find_definition(self, name):
        if name in self._overriden_aliases:
            return self._overriden_aliases[name]

        for level in reversed(self._definitions):
            if name in level:
                return level[name]

        err = "Alias '%s' is not defined here" % name
        raise XmlTemplateError(err)

    def process_aliases(self, element):
        """ Expand aliases within an element and its children

            This method will iterate through the element tree that is
            passed and expand aliases in all the text content and
            attributes.
        """
        if element.text != None:
            element.text = self.expand_aliases(element.text)

        if element.tail != None:
            element.tail = self.expand_aliases(element.tail)

        for name, value in element.attrib.iteritems():
            element.set(name, self.expand_aliases(value))

        if element.tag == "define":
            for alias in element.getchildren():
                name = alias.attrib["name"].strip()
                if "value" in alias.attrib:
                    value = alias.attrib["value"].strip()
                else:
                    value = etree.tostring(element, method="text").strip()
                self.define_alias(name, value)
            parent = element.getparent()
            parent.remove(element)
            return

        self.add_namespace_level()

        for child in element.getchildren():
            self.process_aliases(child)

        # do not drop alias definitions when at top-level so that python
        # tasks are able to access them
        if element.tag != "lnstrecipe":
            self.drop_namespace_level()

    def expand_aliases(self, string):
        while True:
            alias_match = re.search(self._alias_re, string)

            if alias_match:
                template = alias_match.group(0)
                result = self._process_alias_template(template)
                string = string.replace(template, result)
            else:
                break

        return string

    def _process_alias_template(self, string):
        result = None

        alias_match = re.match(self._alias_re, string)
        if alias_match:
            alias_name = alias_match.group(1)
            result = self._find_definition(alias_name)

        return result

    def expand_functions(self, string, node=None):
        """ Process a string and expand it into a XmlTemplateString """

        parts = self._partition_string(string)
        value = XmlTemplateString(node=node)

        for part in parts:
            value.add_part(part)

        return value

    def _partition_string(self, string):
        """ Process templates in a string

            This method will process and expand all template functions
            in a string.

            The function returns an array of string partitions and
            unresolved template functions for further processing.
        """

        result = None

        func_match  = re.search(self._func_re, string)
        if func_match:
            prefix = string[0:func_match.start(0)]
            suffix = string[func_match.end(0):]

            template = func_match.group(0)
            func = self._process_func_template(template)

            return self._partition_string(prefix) + [func] + \
                   self._partition_string(suffix)

        return [string]

    def _process_func_template(self, string):
        func_match = re.match(self._func_re, string)
        if func_match:
            func_name = func_match.group(1)
            func_args = func_match.group(2)

            if func_args == None:
                func_args = []
            else:
                func_args = func_args.split(",")

            param_values = []
            for param in func_args:
                param = param.strip()
                if re.match(self._alias_re, param):
                    param = self._process_alias_template(param)
                param_values.append(param)

            if func_name not in self._func_map:
                msg = "Unknown template function '%s'." % func_name
                raise XmlTemplateError(msg)

            func = self._func_map[func_name](param_values, self._machines)
            return func
        else:
            msg = "The passed string is not a template function."
            raise XmlTemplateError(msg)
