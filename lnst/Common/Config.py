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
import re
import subprocess
from lnst.Common.Utils import bool_it
from lnst.Common.NetUtils import verify_mac_address
from lnst.Common.Colours import get_preset_conf

DefaultRPCPort = 9999

LNSTMajorVersion = '11'

class ConfigError(Exception):
    pass

class Config():
    options = None
    _scheme = None

    def __init__(self):
        self._options = dict()
        self.version = self._get_version()

    def _get_version(self):
        # Check if I'm in git
        try:
            cwd = os.getcwd()
            abspath = os.path.abspath(__file__)
            dname = os.path.dirname(abspath)
            os.chdir(dname)
            head = subprocess.check_output(['git', 'rev-parse', 'HEAD']).strip()
            return head
        except subprocess.CalledProcessError:
            return LNSTMajorVersion
        finally:
            os.chdir(cwd)

    def controller_init(self):
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

        self._options['perfrepo'] = dict()
        self._options['perfrepo']['url'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPlain,
                "name" : "url"
                }
        self._options['perfrepo']['username'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPlain,
                "name" : "username"
                }
        self._options['perfrepo']['password'] = {\
                "value" : "",
                "additive" : False,
                "action" : self.optionPlain,
                "name" : "password"
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

    def slave_init(self):
        self._options['environment'] = dict()
        self._options['environment']['log_dir'] = {\
                "value" : os.path.abspath(os.path.join(
                    os.path.dirname(sys.argv[0]), './Logs')),
                "additive" : False,
                "action" : self.optionPath,
                "name" : "log_dir"}
        self._options['environment']['use_nm'] = {\
                "value" : True,
                "additive" : False,
                "action" : self.optionBool,
                "name" : "use_nm"}
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

    def colours_scheme(self):
        self._options['colours'] = dict()
        self._options['colours']["disable_colours"] = {\
                "value": False, "additive": False,
                "action": self.optionBool, "name": "disable_colours"}

        for preset in ["faded", "alert", "highlight", "pass", "fail", "error",
                       "info", "debug", "warning", "log_header"]:
            self._options['colours'][preset] = {\
                    "value": get_preset_conf(preset), "additive": False,
                    "action": self.optionColour, "name": preset}

    def get_config(self):
        return self._options

    def get_section(self, section):
        if section not in self._options:
            msg = 'Unknow section: %s' % section
            raise ConfigError(msg)
        return self._options[section]

    def get_section_values(self, section):
        if section not in self._options:
            msg = 'Unknow section: %s' % section
            raise ConfigError(msg)

        res = {}
        for opt_name, opt in self._options[section].items():
            res[opt_name] = opt["value"]
        return res

    def get_option(self, section, option):
        sect = self.get_section(section)
        if option not in sect:
            msg = 'Unknown option: %s in section: %s' % (option, section)
            raise ConfigError(msg)
        return sect[option]["value"]

    def set_option(self, section, option, value):
        sect = self.get_section(section)
        sect[option]["value"] = value

    def _preprocess_lines(self, lines):
        comment_re = re.compile(r'^#.*$')
        empty_line_re = re.compile(r'^\s*$')
        result = []
        for line in lines:
            if comment_re.match(line):
                continue
            if empty_line_re.match(line):
                continue
            result.append(line.strip())
        return result

    def _parse_file(self, path):
        result = {}
        current_section = None

        section_re = re.compile(r'^\[(\w+)\]$')
        option_re = re.compile(r'^(\w+)\s*(\+?=)\s*(.*)$')
        with open(path, "r") as f:
            lines = f.readlines()

        lines = self._preprocess_lines(lines)
        for line in lines:
            section = section_re.match(line)
            option = option_re.match(line)
            if section:
                current_section = section.group(1)
                if current_section in result:
                    raise ConfigError("Section '[%s]' already defined." %\
                                      current_section)
                result[current_section] = []
            elif option:
                if current_section is None:
                    raise ConfigError("No section defined yet.")
                opt = {"name": option.group(1),
                       "operator": option.group(2),
                       "value": option.group(3)}
                result[current_section].append(opt)
            else:
                msg = "Invalid format of config line:\n%s" % line
                raise ConfigError(msg)
        return result

    def load_config(self, path):
        '''Parse and load the config file'''
        exp_path = os.path.expanduser(path)
        abs_path = os.path.abspath(exp_path)
        print >> sys.stderr, "Loading config file '%s'" % abs_path
        sections = self._parse_file(abs_path)

        self.handleSections(sections, abs_path)

    def handleSections(self, sections, path):
        for section in sections:
            if section in self._options:
                if section == "pools":
                    self.handlePools(sections[section], path)
                else:
                    self.handleOptions(section, sections[section], path)
            else:
                msg = "Unknown section: %s" % section
                raise ConfigError(msg)

    def handleOptions(self, section_name, config, cfg_path):
        section = self._options[section_name]

        for opt in config:
            opt_name = opt["name"]
            opt_operator = opt["operator"]
            opt_value = opt["value"]
            if not opt_value:
                continue
            option = self._find_option_by_name(section, opt_name)
            if option != None:
                if opt_operator == "=":
                    option["value"] = option["action"](opt_value, cfg_path)
                elif opt_operator == "+=" and option["additive"]:
                    option["value"] += option["action"](opt_value, cfg_path)
                elif opt_operator == "+=":
                    msg = "Operator += not allowed for option %s" % opt_name
                    raise ConfigError(msg)
            else:
                msg = "Unknown option: %s in section %s" % (opt_name,
                                                            section_name)
                raise ConfigError(msg)

    def handlePools(self, config, cfg_path):
        for pool in config:
            if pool["operator"] != "=":
                msg = "Only opetator '=' is allowed for section pools."
                raise ConfigError(msg)
            self.add_pool(pool["name"], pool["value"], cfg_path)

    def add_pool(self, pool_name, pool_dir, cfg_path):
        pool = {"value" : self.optionPath(pool_dir, cfg_path),
                "additive" : False,
                "action" : self.optionPath,
                "name" : pool_name}
        self._options["pools"][pool_name] = pool

    def get_pools(self):
        pools = {}
        for pool_name, pool in self._options["pools"].items():
            pools[pool_name] = pool["value"]
        return pools

    def get_pool(self, pool_name):
        try:
            return self._options["pools"][pool_name]
        except KeyError:
            return None

    def _find_option_by_name(self, section, opt_name):
        for option in section.itervalues():
            if option["name"] == opt_name:
                return option
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

    def optionPlain(self, option, cfg_path):
        return option

    def dump_config(self):
        string = ""
        for section in self._options:
            string += "[%s]\n" % section
            for option in self._options[section]:
                val = self.value_to_string(section, option)
                opt_name = self._options[section][option]["name"]
                string += "%s = %s\n" % (opt_name, val)

        return string

    def value_to_string(self, section, option):
        string = ""
        value = self._options[section][option]["value"]

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
