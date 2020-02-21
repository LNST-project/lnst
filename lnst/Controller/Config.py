"""
Defines the CtlConfig class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import sys
from lnst.Common.Config import DefaultRPCPort, Config

class CtlConfig(Config):
    """Configuration scheme used by the Controller"""
    def _init_options(self):
        self._options['environment'] = dict()
        self._options['environment']['mac_pool_range'] = {\
                "value" : ['52:54:01:00:00:01', '52:54:01:FF:FF:FF'],
                "additive" : False,
                "action" : self.optionMacRange,
                "name" : "mac_pool_range"}
        self._options['environment']['rpcport'] = {\
                "value" : DefaultRPCPort,
                "additive" : False,
                "action" : self.optionPort,
                "name" : "rpcport"}
        self._options['environment']['tool_dirs'] = {\
                "value" : [],
                "additive" : True,
                "action" : self.optionDirList,
                "name" : "test_tool_dirs"}
        self._options['environment']['module_dirs'] = {\
                "value" : [],
                "additive" : True,
                "action" : self.optionDirList,
                "name" : "test_module_dirs"}
        self._options['environment']['log_dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './Logs')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "log_dir"}
        self._options['environment']['resource_dir'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPath,
                "name" : "resource_dir"}
        self._options['environment']['xslt_url'] = {
                "value" : "http://www.lnst-project.org/files/result_xslt/xml_to_html.xsl",
                "additive" : False,
                "action" : self.optionPlain,
                "name" : "xslt_url"
                }
        self._options['environment']['allow_virtual'] = {
                "value" : False,
                "additive" : False,
                "action" : self.optionBool,
                "name" : "allow_virtual"
                }

        self._options['pools'] = dict()

        self._options['security'] = dict()
        self._options['security']['identity'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPlain,
                "name" : "identity"}
        self._options['security']['privkey'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPath,
                "name" : "privkey"}

        self.colours_scheme()
