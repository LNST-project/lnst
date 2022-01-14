"""
Defines the AgentConfig class.

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

class AgentConfig(Config):
    def _init_options(self):
        self._options['environment'] = dict()
        self._options['environment']['log_dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './Logs')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "log_dir"}
        self._options['environment']['rpcport'] = {\
                "value" : DefaultRPCPort,
                "additive" : False,
                "action" : self.optionPort,
                "name" : "rpcport"}

        self._options['cache'] = dict()
        self._options['cache']['dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './cache')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "cache_dir"}

        self._options['cache']['expiration_period'] = {\
                "value" : 7*24*60*60, # 1 week
                "additive" : False,
                "action" : self.optionTimeval,
                "name" : "expiration_period"}

        self._options['security'] = dict()
        self._options['security']['auth_types'] = {\
                "value" : "none",
                "additive" : False,
                "action" : self.optionPlain, #TODO list??
                "name" : "auth_types"}
        self._options['security']['auth_password'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPlain,
                "name" : "auth_password"}
        self._options['security']['privkey'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPath,
                "name" : "privkey"}
        self._options['security']['ctl_pubkeys'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPath,
                "name" : "ctl_pubkeys"}

        self.colours_scheme()
