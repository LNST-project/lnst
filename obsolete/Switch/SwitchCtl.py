"""
This module defines SwitchCtl class useful for switch controlling

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import logging
import copy
import imp
from SwitchConfigParse import SwitchConfigParse

class SwitchCtl:
    def __init__(self, config_xml):
        parse = SwitchConfigParse()
        self._config = parse.parse_switch_config(config_xml)

    def dump_config(self):
        return copy.deepcopy(self._config)

    def _set_driver(self):
        driver_name = self._config["info"]["driver"]
        path = "Switch/Drivers/%s" % driver_name
        fp, pathname, description = imp.find_module(path)
        module = imp.load_module(path, fp, pathname, description)
        driver_class = getattr(module, driver_name)
        self._driver = driver_class(self._config)

    def init(self):
        self._set_driver()
        self._driver.init()

    def configure(self):
        self._driver.configure()

    def cleanup(self):
        self._driver.cleanup()
