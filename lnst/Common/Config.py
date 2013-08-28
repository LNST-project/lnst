"""
Module containing class used for loading config files.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import os
import sys
import logging
import re
from ConfigParser import ConfigParser
from lnst.Common.Utils import bool_it
from lnst.Common.NetUtils import verify_ip_address, verify_mac_address
from lnst.Common.Colours import get_preset_conf

DefaultRPCPort = 9999

class ConfigError(Exception):
    pass

class Config():
    options = None
    _scheme = None

    def __init__(self):
        self.options = dict()

    def controller_init(self):
        self.options['environment'] = dict()
        self.options['environment']['mac_pool_range'] = {\
                "value" : ['52:54:01:00:00:01', '52:54:01:FF:FF:FF'],
                "additive" : False,
                "action" : self.optionMacRange,
                "name" : "mac_pool_range"}
        self.options['environment']['rpcport'] = {\
                "value" : DefaultRPCPort,
                "additive" : False,
                "action" : self.optionPort,
                "name" : "rpcport"}
        self.options['environment']['pool_dirs'] = {\
                "value" : [],
                "additive" : True,
                "action" : self.optionDirList,
                "name" : "machine_pool_dirs"}
        self.options['environment']['tool_dirs'] = {\
                "value" : [],
                "additive" : True,
                "action" : self.optionDirList,
                "name" : "test_tool_dirs"}
        self.options['environment']['module_dirs'] = {\
                "value" : [],
                "additive" : True,
                "action" : self.optionDirList,
                "name" : "test_module_dirs"}
        self.options['environment']['log_dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './Logs')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "log_dir"}
        self.options['environment']['resource_dir'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPath,
                "name" : "resource_dir"}

        self.colours_scheme()

    def slave_init(self):
        self.options['environment'] = dict()
        self.options['environment']['log_dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './Logs')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "log_dir"}
        self.options['environment']['use_nm'] = {\
                "value" : True,
                "additive" : False,
                "action" : self.optionBool,
                "name" : "use_nm"}

        self.options['cache'] = dict()
        self.options['cache']['dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './cache')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "cache_dir"}

        self.options['cache']['expiration_period'] = {\
                "value" : 7*24*60*60, # 1 week
                "additive" : False,
                "action" : self.optionTimeval,
                "name" : "expiration_period"}

        self.colours_scheme()

    def colours_scheme(self):
        self.options['colours'] = dict()
        self.options['colours']["disable_colours"] = {\
                "value": False, "additive": False,
                "action": self.optionBool, "name": "disable_colours"}

        for preset in ["faded", "alert", "highlight", "pass", "fail", "error",
                       "info", "debug", "warning", "log_header"]:
            self.options['colours'][preset] = {\
                    "value": get_preset_conf(preset), "additive": False,
                    "action": self.optionColour, "name": preset}

    def get_config(self):
        return self.options

    def get_section(self, section):
        if section not in self.options:
            msg = 'Unknow section: %s' % section
            raise ConfigError(msg)
        return self.options[section]

    def get_option(self, section, option):
        sect = self.get_section(section)
        if option not in sect:
            msg = 'Unknown option: %s in section: %s' % (option, section)
            raise ConfigError(msg)
        return sect[option]["value"]

    def load_config(self, path):
        '''Parse and load the config file'''
        exp_path = os.path.expanduser(path)
        abs_path = os.path.abspath(exp_path)
        parser = ConfigParser(dict_type=dict)
        parser.read(abs_path)

        sections = parser._sections

        self.handleSections(sections, abs_path)

    def handleSections(self, sections, path):
        for section in sections:
            if section in self.options:
                self.handleOptions(section, sections[section], path)
            else:
                msg = "Unknown section: %s" % section
                raise ConfigError(msg)

    def handleOptions(self, section_name, config, cfg_path):
        section = self.options[section_name]

        config.pop('__name__', None)
        for opt in config:
            option = self._find_option_by_name(section, opt)
            if option != None:
                if option[1]: #additive?
                    option[0]["value"] +=\
                            option[0]["action"](config[opt], cfg_path)
                else:
                    option[0]["value"] =\
                            option[0]["action"](config[opt], cfg_path)
            else:
                msg = "Unknown option: %s in section %s" % (opt, section_name)
                raise ConfigError(msg)

    def _find_option_by_name(self, section, opt_name):
        match = re.match(r'^(\w*)(\s+\+)$', opt_name)
        if match != None:
            additive = True
            opt_name = match.groups()[0]
        else:
            additive = False

        for option in section.itervalues():
            if option["name"] == opt_name:
                if (not option["additive"]) and additive:
                    msg = "Operator += cannot be used in option %s" % opt_name
                    raise ConfigError(msg)
                return (option, additive)

        return None

    def optionPort(self, option, cfg_path):
        try:
            int(option)
        except ValueError:
            msg = "Option port expects a number."
            raise ConfigError(msg)
        return int(option)

    def optionPath(self, option, cfg_path):
        exp_path = os.path.expanduser(option)
        abs_path = os.path.join(os.path.dirname(cfg_path), exp_path)
        norm_path = os.path.normpath(abs_path)
        return norm_path

    def optionMacRange(self, option, cfg_path):
        vals = option.split()
        if len(vals) != 2:
            msg = "Option mac_pool_range expects 2"\
                    " values sepparated by whitespaces."
            raise ConfigError(msg)
        if not verify_mac_address(vals[0]):
            msg = "Invalid MAC address: %s" % vals[0]
            raise ConfigError(msg)
        if not verify_mac_address(vals[1]):
            msg = "Invalid MAC address: %s" % vals[1]
            raise ConfigError(msg)
        return vals

    def optionDirList(self, option, cfg_path):
        paths = re.split(r'(?<!\\)\s', option)

        dirs = []
        for path in paths:
            if path == '':
                continue
            norm_path = self.optionPath(path, cfg_path)
            dirs.append(norm_path)

        return dirs

    def optionTimeval(self, option, cfg_path):
        timeval_re = "^(([0-9]+)days?)?\s*(([0-9]+)hours?)?\s*" \
                     "(([0-9]+)minutes?)?\s*(([0-9]+)seconds?)?$"
        timeval_match = re.match(timeval_re, option)
        if timeval_match:
            values = timeval_match.groups()
            timeval = 0
            if values[1]:
                timeval += int(values[1])*24*60*60
            if values[3]:
                timeval += int(values[3])*60*60
            if values[5]:
                timeval += int(values[5])*60
            if values[7]:
                timeval += int(values[7])
        else:
            msg = "Incorrect timeval format."
            raise ConfigError(msg)

        return timeval

    def optionColour(self, option, cfg_path):
        colour = option.split()
        if len(colour) != 3:
            msg = "Colour must be specified by 3"\
                    " values (foreground, background, bold)"\
                    " sepparated by whitespace."
            raise ConfigError(msg)

        return colour

    def optionBool(self, option, cfg_path):
        return bool_it(option)

    def dump_config(self):
        string = ""
        for section in self.options:
            string += "[%s]\n" % section
            for option in self.options[section]:
                val = self.value_to_string(section, option)
                opt_name = self.options[section][option]["name"]
                string += "%s = %s\n" % (opt_name, val)

        return string

    def value_to_string(self, section, option):
        string = ""
        value = self.options[section][option]["value"]

        if type(value) == list:
            string = " ".join(value)
        else:
            string = str(value)

        return string

#Global object containing lnst configuration, available across modules
#The object is created here but the contents are initialized
#in lnst-ctl and lnst-slave, after that the modules that need the configuration
#just import this object
lnst_config = Config()
