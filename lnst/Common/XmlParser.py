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
import sys
import logging
from lxml import etree
from lnst.Common.XmlTemplates import XmlTemplates, XmlTemplateError
from lnst.Common.XmlProcessing import XmlProcessingError, XmlData

class XmlParser(object):
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
        try:
            doc = etree.parse(self._path)
            doc.xinclude()
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

        root_tag = doc.getroot()
        self._template_proc.process_aliases(root_tag)

        try:
            self._schema.assertValid(doc)
        except:
            err = self._schema.error_log[0]
            loc = {"file": os.path.basename(err.filename),
                   "line": err.line, "col": err.column}
            exc = XmlProcessingError(err.message)
            exc.set_loc(loc)
            raise exc

        return self._process(root_tag)

    def _process(self, root_tag):
        pass

    def set_machines(self, machines):
        self._template_proc.set_machines(machines)

    def _has_attribute(self, element, attr):
        return attr in element.attrib

    def _get_attribute(self, element, attr):
        return self._template_proc.expand_functions(element.attrib[attr])

    def _get_content(self, element):
        text = etree.tostring(element, method="text")
        return self._template_proc.expand_functions(text)
