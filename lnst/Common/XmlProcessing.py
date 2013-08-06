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

class XmlProcessingError(Exception):
    """ Exception thrown on parsing errors """

    _filename = None
    _line = None
    _col = None

    def __init__(self, msg, obj=None):
        super(XmlProcessingError, self).__init__()

        self._msg = msg

        if obj and hasattr(obj, "loc"):
            self.set_loc(obj.loc)

        #logging.error(self.__str__())

    def set_loc(self, loc):
        self._filename = loc["file"]
        self._line = loc["line"]
        #self._col = loc["col"]

    def __str__(self):
        line = ""
        col = ""
        sep = ""
        loc = ""
        filename = "<unknown>"

        if self._filename:
            filename = self._filename

        if self._line:
            line = "%d" % self._line
            sep = ":"

        if self._col:
            col = "%s%d" % (sep, self._col)

        if self._line or self._col:
            loc = "%s%s:" % (line, col)

        return "%s:%s %s" % (filename, loc, self._msg)

class XmlDataIterator:
    def __init__(self, iterator):
        self._iterator = iterator

    def __iter__(self):
        return self

    def next(self):
        n = self._iterator.next()

        # For normal iterators
        if type(n) == XmlTemplateString:
            return str(n)

        # For iteritems() iterators
        if type(n) == tuple and len(n) == 2 and type(n[1]) == XmlTemplateString:
            return (n[0], str(n[1]))

        return n

class XmlCollection(list):
    def __init__(self, node=None):
        super(XmlCollection, self).__init__()
        if node:
            self.loc = node.loc

    def __getitem__(self, key):
        value = super(XmlCollection, self).__getitem__(key)
        if type(value) == XmlData or type(value) == XmlCollection:
            return value

        return str(value)

    def __iter__(self):
        it = super(XmlCollection, self).__iter__()
        return XmlDataIterator(it)

class XmlData(dict):
    def __init__(self, node=None):
        super(XmlData, self).__init__()
        if node:
            self.loc = node.loc

    def __getitem__(self, key):
        value = super(XmlData, self).__getitem__(key)
        if type(value) == XmlData or type(value) == XmlCollection:
            return value

        return str(value)

    def __iter__(self):
        it = super(XmlData, self).__iter__()
        return XmlDataIterator(it)

    def iteritems(self):
        it = super(XmlData, self).iteritems()
        return XmlDataIterator(it)

    def iterkeys(self):
        it = super(XmlData, self).iterkeys()
        return XmlDataIterator(it)

    def itervalues(self):
        it = super(XmlData, self).itervalues()
        return XmlDataIterator(it)

class XmlTemplateString(object):
    def __init__(self, param=None, node=None):
        if type(param) == str:
            self._parts = [param]
        elif type(param) == list:
            self._parts = param
        else:
            self._parts = []

        if node and hasattr(node, "loc"):
            self.loc = node.loc

    def __add__(self, other):
        if type(other) is str:
            self.add_part(other)
        elif type(other) is self.__class__:
            self._parts += other._parts
        else:
            raise XmlProcessingError("Cannot concatenate %s and %s" % \
                                     str(type(self)), str(type(other)))
        return self

    def __str__(self):
        string = ""
        for part in self._parts:
            string += str(part)
        return string

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return str(self) != str(other)

    def __len__(self):
        return len(str(self))

    def add_part(self, part):
        self._parts.append(part)

class XmlDomTreeInit:
    """ Handles creation/initialization of DOM trees

        It allows you to parse XML file or string into a DOM tree.
        It also adds an extra parameter to each node of the tree
        called `loc' which can be used to determine where exactly
        was the element placed in the original source XML file.
        This is useful for error reporting.
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
            loc = {"file": self._filename,
                   "line": self._sax.getLineNumber(),
                   "col": self._sax.getColumnNumber()}
            cur_elem.loc = loc

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
        self._filename = os.path.basename(filename)
        try:
            dom = parseString(xml_text, self._sax)
        except sax.SAXParseException as err:
            loc = {"file": self._filename,
                   "line": err.getLineNumber(),
                   "col": err.getColumnNumber()}
            exc = XmlProcessingError(err.getMessage())
            exc.set_loc(loc)
            raise exc

        loc = {"file": self._filename, "line": 0, "col": 0}
        dom.loc = loc
        return dom
