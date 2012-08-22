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

class XmlTemplateError(Exception):
    pass

class XmlTemplates:
    """ This class serves as template processor """

    _alias_re = "\{\$([a-zA-Z0-9_]+)(\[[^{}]+\])?\}"
    _func_re  = "\{([a-zA-Z0-9_]+)\(([^\(\)]*)\)\}"

    def __init__(self, definitions=None):
        if definitions:
            self._definitions = [definitions]
        else:
            self._definitions = [{}]

        self._reserved_aliases = ["recipe"]

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

    def define_alias(self, name, value, skip_reserved_check=False):
        """ Associate an alias name with some value

        The value can be of an atomic type or an array. The
        definition is added to the current namespace level.
        """

        if not name in self._reserved_aliases \
           or skip_reserved_check == True:
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
        for level in reversed(self._definitions):
            if name in level:
                return level[name]

        err = "'%s' is not defined here" % name
        raise XmlTemplateError(err)

    def expand_dom(self, node):
        """
        Traverse DOM tree from `node' down and expand any
        templates along the way.
        """

        if node.nodeType == node.ELEMENT_NODE:
            i = 0
            num_attributes = node.attributes.length
            while(i < num_attributes):
                attr = node.attributes.item(i)
                attr.value = self.expand_string(str(attr.value))
                i += 1
        elif node.nodeType == node.TEXT_NODE:
            node.data = self.expand_string(str(node.data))

        for child in node.childNodes:
            self.expand_dom(child)

    def expand_group(self, group):
        """
        Behaves exactly the same as the `expand' method, but it
        operates on a group of DOM nodes stored within a list,
        rather than a single node.
        """

        for node in group:
            self.expand_dom(node)

    def expand_string(self, string):
        """ Expand templates in a string

            This method will process and expand all templates
            contained inside a string.
        """
        while True:
            alias_match = re.search(self._alias_re, string)
            func_match  = re.search(self._func_re, string)

            result = None

            if alias_match:
                template = alias_match.group(0)
                result = self._process_alias_template(template)
            elif func_match:
                template = func_match.group(0)
                result = self._process_func_template(template)
            else:
                break

            string = string.replace(template, result)

        return string

    def _process_alias_template(self, string):
        result = None

        alias_match = re.match(self._alias_re, string)
        if alias_match:
            alias_name = alias_match.group(1)
            array_subscript = alias_match.group(2)

            alias_obj = self._find_definition(alias_name)

            if array_subscript != None:
                try:
                    result = str(eval("alias_obj%s" % array_subscript))
                except (KeyError, IndexError):
                    err = "Wrong array subscript in '%s%s'" \
                                % (alias_name, array_subscript)
                    raise XmlTemplateError(err)
            else:
                result = alias_obj

        return result

    def _process_func_template(self, string):
        result = None

        func_match = re.match(self._func_re, string)
        if func_match:
            func_name = func_match.group(1)
            func_params = func_match.group(2)

            if func_params == None:
                func_params = []
            else:
                func_params = func_params.split(",")

            param_values = []
            for param in func_params:
                param = param.strip()
                if re.match(self._alias_re, param):
                    param = self._process_alias_template(param)
                param_values.append(param)

            result = self._call_preprocessor_func(func_name, param_values)

        return result

    def _call_preprocessor_func(self, name, params):
        if name == "ip":
            result = self._ip_func(params)
        elif name == "hwaddr":
            result = self._hwaddr_func(params)
        elif name == "devname":
            result = self._devname_func(params)
        else:
            raise XmlTemplateError("Unknown preprocessor function '%s'" % name)

        return result

    def _ip_func(self, params):
        self._validate_func_params("ip", params, 2, 1)
        recipe = self._get_recipe_data("ip")

        m_id = params[0]
        if_id = params[1]
        ip_id = int(params[2]) if len(params) == 3 else 0

        if 'machines' not in recipe or m_id not in recipe['machines']:
            msg = "First parameter of function ip() is invalid: "\
                    "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)
        machine = recipe["machines"][m_id]


        if if_id not in machine['netconfig']:
            msg = "Second parameter of function ip() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)
        if ip_id >= len(machine['netconfig'][if_id]['addresses']):
            msg = "Third parameter of function ip() is invalid: "\
                    "Address %s does not exist." % ip_id
            raise XmlTemplateError(msg)
        ip_addr = machine['netconfig'][if_id]['addresses'][ip_id]


        return ip_addr.split('/')[0]

    def _hwaddr_func(self, params):
        self._validate_func_params("hwaddr", params, 2, 0)
        recipe = self._get_recipe_data("hwaddr")
        m_id = params[0]
        if_id = params[1]

        if 'machines' not in recipe or m_id not in recipe['machines']:
            msg = "First parameter of function hwaddr() is invalid: "\
                    "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)
        machine = recipe["machines"][m_id]

        if if_id not in machine['netconfig']:
            msg = "Second parameter of function hwaddr() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)
        mac_addr = machine['netconfig'][if_id]['hwaddr']

        return mac_addr


    def _devname_func(self, params):
        self._validate_func_params("devname", params, 2, 0)
        recipe = self._get_recipe_data("devname")
        m_id = params[0]
        if_id = params[1]

        if 'machines' not in recipe or m_id not in recipe['machines']:
            msg = "First parameter of function devname() is invalid: "\
                    "Machine %s does not exist." % m_id
            raise XmlTemplateError(msg)
        machine = recipe["machines"][m_id]

        if if_id not in machine['netconfig']:
            msg = "Second parameter of function devname() is invalid: "\
                    "Interface %s does not exist." % if_id
            raise XmlTemplateError(msg)
        dev_name = machine['netconfig'][if_id]['name']

        return dev_name

    @staticmethod
    def _validate_func_params(name, params, mandatory, optional):
        num_params = len(params)
        if num_params > (mandatory + optional) or num_params < mandatory:
            if optional:
                err = "Function %s takes between %d-%d arguments, %d passed" \
                        % (name, mandatory, mandatory + optional, num_params)
            else:
                err = "Function %s takes %d arguments, %d passed" \
                            % (name, mandatory, num_params)
            raise XmlTemplateError(err)
        for param in params[2:]:
            try:
                int(param)
            except ValueError:
                err = "Non-integer parameter passed to '%s'" % name
                raise XmlTemplateError(err)

    def _get_recipe_data(self, template_name):
        try:
            recipe = self._find_definition("recipe")
            return recipe
        except XmlTemplateError, err:
            msg = "Cannot resolve %s(): " % template_name
            msg += str(err)
            raise XmlTemplateError(msg)
