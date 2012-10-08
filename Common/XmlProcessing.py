"""
This module contains code code for XML parsing and processing.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import os
import logging
from xml.dom.minidom import parseString
from xml import sax
from Common.XmlTemplates import XmlTemplates, XmlTemplateError
from Common.RecipePath import RecipePath


class XmlProcessingError(Exception):
    """ Exception thrown on parsing errors """

    _filename = None
    _line = None
    _col = None

    def __init__(self, msg, node=None):
        super(XmlProcessingError, self).__init__()

        self._msg = msg

        if node and hasattr(node, "parse_position"):
            self.set_pos(node.parse_position)

        #logging.error(self.__str__())

    def set_pos(self, pos):
        self._filename = pos["file"]
        self._line = pos["line"]
        #self._col = pos["col"]

    def __str__(self):
        line = ""
        col = ""
        sep = ""
        pos = ""
        filename = "<unknown>"

        if self._filename:
            filename = self._filename

        if self._line:
            line = "%d" % self._line
            sep = ":"

        if self._col:
            col = "%s%d" % (sep, self._col)

        if self._line or self._col:
            pos = "%s%s:" % (line, col)

        return "XmlProcessingError:%s:%s %s" % (filename, pos, self._msg)

class XmlDomTreeInit:
    """ Handles creation/initialization of DOM trees

        It allows you to parse XML file or string into a DOM tree.
        It also adds an extra parameter to each node of the tree
        called `parse_position' which can be used to determine
        where exactly was the element placed in the original source
        XML file. This is useful for error reporting.
    """

    _sax = None
    _filename = None
    __orig_set_content_handler = None

    def __init__(self):
        self._init_sax()

    def _init_sax(self):
        parser = sax.make_parser()
        self.__orig_set_content_handler = parser.setContentHandler
        parser.setContentHandler = self.__set_content_handler
        self._sax = parser

    def __set_content_handler(self, dom_handler):
        def start_element_ns(name, tag_name , attrs):
            orig_start_cb(name, tag_name, attrs)
            cur_elem = dom_handler.elementStack[-1]
            pos = {"file": self._filename,
                   "line": self._sax.getLineNumber(),
                   "col": self._sax.getColumnNumber()}
            cur_elem.parse_position = pos

        orig_start_cb = dom_handler.startElementNS
        dom_handler.startElementNS = start_element_ns
        self.__orig_set_content_handler(dom_handler)

    @staticmethod
    def _load_file(filename):
        handle = open(filename, "r")
        data = handle.read()
        handle.close()
        return data

    def parse_file(self, xml_filepath):
        xml_text = self._load_file(xml_filepath)
        filename = os.path.basename(xml_filepath)
        return self.parse_string(xml_text, filename)

    def parse_string(self, xml_text, filename="xml_string"):
        self._filename = filename
        try:
            dom = parseString(xml_text, self._sax)
        except sax.SAXParseException, err:
            pos = {"file": filename,
                   "line": err.getLineNumber(),
                   "col": err.getColumnNumber()}
            exc = XmlProcessingError(err.getMessage())
            exc.set_pos(pos)
            raise exc

        return dom


class XmlParser(object):
    """ Parent class for XML processors

        This class handles manipulation of XML DOM objects
        that are used for processing XML files.

        The standard DOM objects are extended with position data
        (file name, line number and column number) that can be
        used in error reporting.
    """

    def _process_child_nodes(self, parent, scheme, params=None):
        child_nodes = parent.childNodes

        if not params:
            params = {}

        for node in child_nodes:
            if node.nodeType == node.COMMENT_NODE or \
               node.nodeType == node.TEXT_NODE:
                continue
            elif node.nodeType == node.ELEMENT_NODE:
                node_name = node.nodeName
                if node_name in scheme:
                    handler = scheme[node_name]
                    self._process_node(node, handler, params)
                else:
                    msg = "Unexpected '%s' tag under '%s'" % (node_name,
                                                        parent.nodeName)
                    raise XmlProcessingError(msg, node)
            else:
                msg = "Only XML elements are allowed here!"
                raise XmlProcessingError(msg, node)

    def _process_node(self, node, handler, params):
        handler(node, params)

    @staticmethod
    def _convert_string(node, string, conversion_cb):
        if conversion_cb:
            try:
                converted = conversion_cb(string)
            except ValueError, err:
                raise XmlProcessingError("Conversion error: " + str(err), node)
            return converted

        return string

    def _has_attribute(self, node, attr_name):
        return node.hasAttribute(attr_name)

    def _get_attribute(self, node, attr_name, conversion_cb=None):
        if not self._has_attribute(node, attr_name):
            msg = "Expected attribute '%s' missing" % attr_name
            raise XmlProcessingError(msg, node)
        attr_val = str(node.getAttribute(attr_name))
        return self._convert_string(node, attr_val, conversion_cb)

    def _get_text_content(self, node, conversion_cb=None):
        content = []
        for child in node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                content.append(child.nodeValue)

        text = str(''.join(content).strip())
        return self._convert_string(node, text, conversion_cb)

    def _get_all_attributes(self, node):
        res = {}
        for i in range(0, node.attributes.length):
            attr = node.attributes.item(i)
            res[attr.name] = attr.value

        return res

class RecipeParser(XmlParser):
    """ Enhanced XmlParser

        This class enhances XmlParser with advanced features that are
        used in parsing XML recipe files. All recipe (sub)parsers should
        use this as their base class.
    """

    _recipe = None
    _template_proc = None
    _include_root = None
    _events_enabled = None
    _event_handlers = None

    def __init__(self, parent=None):
        super(RecipeParser, self).__init__()

        if parent:
            self._recipe = parent._recipe
            self._template_proc = parent._template_proc
            self._include_root = parent._include_root
            self._events_enabled = parent._events_enabled
            self._event_handlers = parent._event_handlers
        else:
            self._recipe = {}
            self._template_proc = XmlTemplates()
            self._include_root = os.getcwd()
            self._events_enabled = True
            self._event_handlers = {}

    def set_recipe(self, recipe):
        self._recipe = recipe

    def set_definitions(self, defs):
        self._template_proc.set_definitions(defs)

    def set_include_root(self, include_root_path):
        self._include_root = include_root_path

    def enable_events(self):
        self._events_enabled = True

    def disable_events(self):
        self._events_enabled = False

    def register_event_handler(self, event_id, handler):
        self._event_handlers[event_id] = handler

    def _trigger_event(self, event_id, args):
        if not self._events_enabled:
            return

        try:
            handler = self._event_handlers[event_id]
        except KeyError, err:
            logging.warn("No handler found for %s event, ignoring", event_id)
            return

        handler(**args)

    def _process_child_nodes(self, node, scheme, params=None,
                                    new_ns_level=True):
        scheme["define"] = self._define_handler

        if not params:
            params = {}

        if new_ns_level:
            self._template_proc.add_namespace_level()

        parent = super(RecipeParser, self)
        result = parent._process_child_nodes(node, scheme, params)

        if new_ns_level:
            self._template_proc.drop_namespace_level()

        return result

    def _process_node(self, node, handler, params):
        old_include_root = None
        if self._has_attribute(node, "source"):
            source = self._get_attribute(node, "source")

            source_rp = RecipePath(self._include_root, source)

            old_include_root = self._include_root
            self._include_root = source_rp.get_root()
            xmlstr = source_rp.to_str()

            dom_init = XmlDomTreeInit()
            try:
                dom = dom_init.parse_string(xmlstr,
                                            filename=source_rp.abs_path())
            except IOError, err:
                msg = "Unable to resolve include: %s" % str(err)
                raise XmlProcessingError(msg, node)

            loaded_node = None
            try:
                loaded_node = dom.getElementsByTagName(node.nodeName)[0]
            except Exception:
                msg = ("No '%s' element present in included file '%s'."
                                    % (node.nodeName, source_rp.abs_path()))
                raise XmlProcessingError(msg, node)

            old_attrs = self._get_all_attributes(node)

            parent = node.parentNode
            parent.replaceChild(loaded_node, node)
            node = loaded_node

            # copy all of the original attributes to the sourced node
            for name, value in old_attrs.iteritems():
                # do not overwrite sourced attributes
                if not node.hasAttribute(name):
                    node.setAttribute(name, value)

        parent = super(RecipeParser, self)
        parent._process_node(node, handler, params)

        if old_include_root:
            self._include_root = old_include_root

    def _get_attribute(self, node, attr_name, conversion_cb=None):
        parent = super(RecipeParser, self)
        raw_attr_val = parent._get_attribute(node, attr_name)

        try:
            attr_val = self._template_proc.expand_string(raw_attr_val)
        except XmlTemplateError, err:
            raise XmlProcessingError(str(err), node)

        return self._convert_string(node, attr_val, conversion_cb)

    def _get_text_content(self, node, conversion_cb=None):
        parent = super(RecipeParser, self)
        raw_content = parent._get_text_content(node)

        try:
            content = self._template_proc.expand_string(raw_content)
        except XmlTemplateError, err:
            raise XmlProcessingError(str(err), node)

        return self._convert_string(node, content, conversion_cb)

    def _define_handler(self, node, params):
        scheme = {"alias": self._alias_handler}
        self._process_child_nodes(node, scheme, new_ns_level=False)

    def _alias_handler(self, node, params):
        if self._has_attribute(node, "name"):
            name = self._get_attribute(node, "name")
        else:
            msg = "Alias tag must have the 'name' attribute"
            raise XmlProcessingError(msg, node)

        if self._has_attribute(node, "value"):
            value = self._get_attribute(node, "value")
        else:
            value = self._get_text_content(node)

        try:
            self._template_proc.define_alias(name, value)
        except XmlTemplateError, err:
            raise XmlProcessingError(str(err), node)
