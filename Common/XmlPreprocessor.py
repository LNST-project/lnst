"""
This module contains code for preprocessing templates in XML files/recipes
before they are parsed.

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

class XmlPreprocessor:
    """
    This class serves as template processor within a XML DOM tree object.
    """

    _template_re = "\{([^\{\}]+)\}"
    _alias_re = "^\$([a-zA-Z0-9_]+)(\[.+\])*$"
    _func_re  = "^([a-zA-Z0-9_]+)\(([^\(\)]*)\)$"

    def __init__(self):
        self._definitions = {}
        self._reserved_aliases = ["recipe"]

    def define_alias(self, name, value, skip_reserved_check=False):
        """
        Associate an alias name with some value. The value can be of
        an atomic type or an array.
        """

        if not name in self._reserved_aliases \
           or skip_reserved_check == True:
            self._definitions[name] = value
        else:
            raise XmlTemplateError("Alias name '%s' is reserved" % name)

    def remove_comments(self, node):
        """
        Remove all comment nodes from the tree.
        """

        comments = []
        for child in node.childNodes:
            if child.nodeType == node.COMMENT_NODE:
                comments.append(child)
            else:
                self.remove_comments(child)

        for comment in comments:
            node.removeChild(comment)

    def expand(self, node):
        """
        Traverse DOM tree from `node' down and expand any
        templates along the way.
        """

        if node.nodeType == node.ELEMENT_NODE:
            i = 0
            num_attributes = node.attributes.length
            while(i < num_attributes):
                attr = node.attributes.item(i)
                attr.value = self._expand_string(str(attr.value))
                i += 1
        elif node.nodeType == node.TEXT_NODE:
            node.data = self._expand_string(str(node.data))

        for child in node.childNodes:
            self.expand(child)

    def expand_group(self, group):
        """
        Behaves exactly the same as the `expand' method, but it
        operates on a group of DOM nodes stored within a list,
        rather than a single node.
        """

        for node in group:
            self.expand(node)

    def _expand_string(self, string):
        while True:
            template_match = re.search(self._template_re, string)
            if template_match:
                template_string = template_match.group(0)
                template = template_match.group(1)
                template_result = self._process_template(template)

                string = string.replace(template_string, template_result)
            else:
                break

        return string

    def _process_template(self, string):
        string = string.strip()
        result = None

        if re.match(self._alias_re, string):
            result = self._process_alias_template(string)
            return result

        if re.match(self._func_re, string):
            result = self._process_func_template(string)
            return result

        raise XmlTemplateError("Unknown template type '%s'" % string)

    def _process_alias_template(self, string):
        result = None

        alias_match = re.match(self._alias_re, string)
        if alias_match:
            alias_name = alias_match.group(1)
            array_subscript = alias_match.group(2)

            if not alias_name in self._definitions:
                err = "Alias '%s' is not defined here" % alias_name
                raise XmlTemplateError(err)

            if array_subscript != None:
                try:
                    result = str(eval("self._definitions['%s']%s" \
                                    % (alias_name, array_subscript)))
                except (KeyError, IndexError):
                    err = "Wrong array subscript in '%s[%s]'" \
                                % (alias_name, array_subscript)
                    raise XmlTemplateError(err)
            else:
                result = self._definitions[alias_name]

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
        self._check_recipe_data("ip")

        m_id = int(params[0])
        if_id = int(params[1])
        ip_id = int(params[2]) if len(params) == 3 else 0

        machines = self._definitions["recipe"]["machines"]
        ip_addr = machines[m_id]['netconfig'][if_id]['addresses'][ip_id]

        return ip_addr.split('/')[0]

    def _hwaddr_func(self, params):
        self._validate_func_params("hwaddr", params, 2, 0)
        self._check_recipe_data("hwaddr")
        m_id = int(params[0])
        if_id = int(params[1])

        machines = self._definitions["recipe"]["machines"]
        return machines[m_id]['netconfig'][if_id]['hwaddr']


    def _devname_func(self, params):
        self._validate_func_params("devname", params, 2, 0)
        self._check_recipe_data("devname")
        m_id = int(params[0])
        if_id = int(params[1])

        machines = self._definitions["recipe"]["machines"]
        return machines[m_id]['netconfig'][if_id]['name']

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
        for param in params:
            try:
                int(param)
            except ValueError:
                err = "Non-integer parameter passed to '%s'" % name
                raise XmlTemplateError(err)

    def _check_recipe_data(self, template_name):
        if not "recipe" in self._definitions:
            err = "Cannot resolve %s() here, recipe data not available yet" \
                                % template_name
            raise XmlTemplateError(err)
