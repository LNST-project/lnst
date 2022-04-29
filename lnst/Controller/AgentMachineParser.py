"""
This module defines AgentMachineParser class useful to parse XML machine
descriptions for the agent pool

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import os
from lxml import etree
from lnst.Controller.Common import ControllerError
import lnst


class AgentMachineParser(object):
    def __init__(self, am_path, ctl_config):
        # locate the schema file
        # try git path
        dirname = os.path.join(os.path.dirname(lnst.__file__), '..')
        schema_path = os.path.join(dirname, "schema-am.rng")
        if not os.path.exists(schema_path):
            # try configuration
            res_dir = ctl_config.get_option("environment", "resource_dir")
            schema_path = os.path.join(res_dir, "schema-am.rng")

        if not os.path.exists(schema_path):
            raise Exception("The schema file was not found. " + \
                            "Your LNST installation is corrupt!")

        self._path = am_path
        relaxng_doc = etree.parse(schema_path)
        self._schema = etree.RelaxNG(relaxng_doc)

    def parse(self):
        try:
            doc = self._parse(self._path)
            self._remove_comments(doc)
            self._schema.assertValid(doc)
        except:
            err = self._schema.error_log[0]
            loc = {"file": os.path.basename(err.filename),
                   "line": err.line, "col": err.column}
            exc = XmlProcessingError(err.message)
            exc.set_loc(loc)
            raise exc

        return self._process(doc)

    def _parse(self, path):
        try:
            doc = etree.parse(path)
        except etree.LxmlError as err:
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
        except Exception as err:
            loc = {"file": os.path.basename(self._path),
                   "line": None,
                   "col": None}
            exc = XmlProcessingError(str(err))
            exc.set_loc(loc)
            raise exc

        return doc

    def _remove_comments(self, doc):
        comments = doc.xpath('//comment()')
        for c in comments:
            p = c.getparent()
            if p is not None:
                p.remove(c)

    def _process(self, am_tag):
        am = {}

        # params
        params_tag = am_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            am["params"] = params

        # interfaces
        interfaces_tag = am_tag.find("interfaces")
        if interfaces_tag is not None and len(interfaces_tag) > 0:
            am["interfaces"] = []
            for eth_tag in interfaces_tag:
                interface = self._process_interface(eth_tag)
                am["interfaces"].append(interface)

        security_tag = am_tag.find("security")
        am["security"] = self._process_security(security_tag)
        return am

    def _process_params(self, params_tag):
        params = []
        if params_tag is not None:
            for param_tag in params_tag:
                param = {}
                param["name"] = self._get_attribute(param_tag, "name")
                param["value"] = self._get_attribute(param_tag, "value")
                params.append(param)
        return params

    def _process_interface(self, iface_tag):
        iface = {}
        iface["id"] = self._get_attribute(iface_tag, "id")
        iface["network"] = self._get_attribute(iface_tag, "label")
        iface["type"] = "eth"

        # interface parameters
        params_tag = iface_tag.find("params")
        params = self._process_params(params_tag)
        if len(params) > 0:
            iface["params"] = params

        return iface

    def _process_security(self, sec_tag):
        sec = {}

        if sec_tag is None:
            sec["auth_type"] = "none"
            return sec

        auth_type_tag = sec_tag.find("auth_type")
        sec["auth_type"] = auth_type_tag.text.strip()

        auth_passwd_tag = sec_tag.find("auth_password")
        if auth_passwd_tag is not None:
            sec["auth_passwd"] = auth_passwd_tag.text
        else:
            sec["auth_passwd"] = ""

        key_tag = sec_tag.find("pubkey_path")
        if key_tag is not None:
            path = key_tag.text
            exp_path = os.path.expanduser(path)
            abs_path = os.path.join(os.path.dirname(self._path), exp_path)
            norm_path = os.path.normpath(abs_path)
            sec["pubkey_path"] = norm_path
        else:
            sec["pubkey_path"] = ""

        return sec

    def _get_attribute(self, element, attr):
        return element.attrib[attr].strip()

class XmlProcessingError(ControllerError):
    """ Exception thrown on parsing errors """

    _filename = None
    _line = None
    _col = None

    def __init__(self, msg, obj=None):
        super(XmlProcessingError, self).__init__()
        self._msg = msg

        if obj is not None:
            if hasattr(obj, "loc"):
                self.set_loc(obj.loc)
            elif hasattr(obj, "base") and obj.base != None:
                loc = {}
                loc["file"] = os.path.basename(obj.base)
                if hasattr(obj, "sourceline"):
                    loc["line"] = obj.sourceline
                self.set_loc(loc)

    def set_loc(self, loc):
        self._filename = loc["file"]
        self._line = loc["line"]
        if "col" in loc:
            self._col = loc["col"]

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

        return "Parser error: %s:%s %s" % (filename, loc, self._msg)
