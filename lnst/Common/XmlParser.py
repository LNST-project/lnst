"""
This module contains the XmlParser and LnstParser classes.

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import os
import re
import sys
import logging
import copy
from lxml import etree
from lnst.Common.XmlTemplates import XmlTemplates, XmlTemplateError
from lnst.Common.XmlProcessing import XmlProcessingError, XmlData

class XmlParser(object):
    XINCLUDE_RE = r"\{http\:\/\/www\.w3\.org\/[0-9]{4}\/XInclude\}include"

    def __init__(self, schema_file, xml_path):
        # locate the schema file
        # try git path
        dirname = os.path.dirname(sys.argv[0])
        schema_path = os.path.join(dirname, schema_file)
        if not os.path.exists(schema_path):
            # try configuration
            res_dir = lnst_config.get_option("environment", "resource_dir")
            schema_path = os.path.join(res_dir, schema_file)

        if not os.path.exists(schema_path):
            raise Exception("The recipe schema file was not found. " + \
                            "Your LNST installation is corrupt!")

        self._template_proc = XmlTemplates()

        self._path = xml_path
        relaxng_doc = etree.parse(schema_path)
        self._schema = etree.RelaxNG(relaxng_doc)

    def parse(self):
        doc = self._parse(self._path)
        self._remove_comments(doc)

        # Due to a weird implementation of XInclude in lxml, the
        # XmlParser resolves included documents on it's own.
        #
        # To be able to tell later on where each tag was located
        # in the XML document, we add a '__file' attribute to
        # each element of the tree during the parsing.
        #
        # However, these special attributes are of course not
        # valid according to our schemas. To solve this, a copy of
        # the tree is made and the '__file' attributes are removed
        # before validation.
        #
        # XXX This is a *EXTREMELY* dirty hack. Ideas/proposals
        # for cleaner solutions are more than welcome!
        root_tag = self._init_loc(doc.getroot(), self._path)
        self._expand_xinclude(root_tag, os.path.dirname(self._path))

        self._template_proc.process_aliases(root_tag)

        try:
            self._validate(doc)
        except:
            err = self._schema.error_log[0]
            loc = {"file": os.path.basename(err.filename),
                   "line": err.line, "col": err.column}
            exc = XmlProcessingError(err.message)
            exc.set_loc(loc)
            raise exc

        return self._process(root_tag)

    def _parse(self, path):
        try:
            doc = etree.parse(path)
        except Exception as err:
            # A workaround for cases when lxml (quite strangely)
            # sets the filename to <string>.
            if err.error_log[0].filename == "<string>":
                filename = self._path
            else:
                filename = err.error_log[0].filename
            loc = {"file": os.path.basename(filename),
                   "line": err.error_log[0].line,
                   "col": err.error_log[0].column}
            exc = XmlProcessingError(err.error_log[0].message)
            exc.set_loc(loc)
            raise exc

        return doc

    def _process(self, root_tag):
        pass

    def set_machines(self, machines):
        self._template_proc.set_machines(machines)

    def set_aliases(self, defined, overriden):
        self._template_proc.set_aliases(defined, overriden)

    def _has_attribute(self, element, attr):
        return attr in element.attrib

    def _get_attribute(self, element, attr):
        return self._template_proc.expand_functions(element.attrib[attr])

    def _get_content(self, element):
        text = etree.tostring(element, method="text")
        return self._template_proc.expand_functions(text)

    def _expand_xinclude(self, elem, base_url=""):
        for e in elem:
            if re.match(self.XINCLUDE_RE, str(e.tag)):
                href = os.path.join(base_url, e.get("href"))
                filename = os.path.basename(href)

                doc = self._parse(href)
                self._remove_comments(doc)
                node = doc.getroot()

                node = self._init_loc(node, href)

                if e.tail:
                    node.tail = (node.tail or "") + e.tail
                self._expand_xinclude(node, os.path.dirname(href))

                parent = e.getparent()
                if parent is None:
                    return node

                parent.replace(e, node)
            else:
                self._expand_xinclude(e, base_url)
        return elem

    def _remove_comments(self, doc):
        comments = doc.xpath('//comment()')
        for c in comments:
            p = c.getparent()
            if p is not None:
                p.remove(c)

    def _init_loc(self, elem, filename):
        """ Remove all coment tags from the tree """

        elem.attrib["__file"] = filename
        for e in elem:
            self._init_loc(e, os.path.basename(filename))

        return elem

    def _validate(self, original):
        """
            Make a copy of the tree, remove the '__file' attributes
            and validate against the appropriate schema.

            Very unfortunate solution.
        """
        doc = copy.deepcopy(original)
        root = doc.getroot()

        self._prepare_tree_for_validation(root)
        self._schema.assertValid(doc)

    def _prepare_tree_for_validation(self, elem):
        if "__file" in elem.attrib:
            del elem.attrib["__file"]
        for e in elem:
            self._prepare_tree_for_validation(e)
