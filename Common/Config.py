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
from NetTest.NetTestSlave import DefaultRPCPort
from NetUtils import verify_ip_address, verify_mac_address

class ConfigError(Exception):
    pass

class Config():
    options = None
    _scheme = None

    def __init__(self, scheme):
        self.options = dict()

        self._scheme = scheme
        if self._scheme == "controller":
            self.init_controller()
        elif self._scheme == "slave":
            self.init_slave()
        else:
            msg = "Unknow scheme: '%s', can't set up configuration"\
                    % self._scheme
            raise ConfigError(msg)

    def init_controller(self):
        self.options['log'] = dict()
        self.options['log']['path'] = os.path.abspath(os.path.join(
                os.path.dirname(sys.argv[0]), './Logs'))

        self.options['environment'] = dict()
        self.options['environment']['mac_pool_range'] = \
                ['52:54:01:00:00:01', '52:54:01:FF:FF:FF']
        self.options['environment']['rpcport'] = DefaultRPCPort
        self.options['environment']['pool_dirs'] = []
        self.options['environment']['tool_dirs'] = []
        self.options['environment']['module_dirs'] = []

    def init_slave(self):
        self.options['cache'] = dict()
        self.options['cache']['dir'] = os.path.abspath(os.path.join(
                os.path.dirname(sys.argv[0]), './cache'))

        self.options['cache']['expiration_period'] = 7*24*60*60 # 1 week

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
        return sect[option]

    def load_config(self, path):
        '''Parse and load the config file'''
        exp_path = os.path.expanduser(path)
        abs_path = os.path.abspath(exp_path)
        parser = ConfigParser(dict_type=dict)
        parser.read(abs_path)

        sections = parser._sections

        if self._scheme == "controller":
            self.sectionsCntl(sections, abs_path)
        elif self._scheme == "slave":
            self.sectionsSlave(sections, abs_path)
        else:
            msg = "Unknow scheme: '%s', can't parse sections." \
                    % self._scheme
            raise ConfigError(msg)

    def sectionsCntl(self, sections, path):
        for section in sections:
            if section == "log":
                self.sectionLogs(sections[section], path)
            elif section == "environment":
                self.sectionEnvironment(sections[section], path)
            else:
                msg = "Unknown section: %s" % section
                raise ConfigError(msg)

    def sectionsSlave(self, sections, path):
        for section in sections:
            if section == "cache":
                self.sectionCache(sections[section], path)
            else:
                msg = "Unknown section: %s" % section
                raise ConfigError(msg)

    def sectionLogs(self, config, cfg_path):
        section = self.options['log']

        config.pop('__name__', None)
        for option in config:
            if option == 'path':
                section['path'] = self.optionPath(config[option], cfg_path)
            else:
                msg = "Unknown option: %s in section log" % option
                raise ConfigError(msg)

    def sectionCache(self, config, cfg_path):
        section = self.options['cache']

        config.pop('__name__', None)
        for option in config:
            if option == 'cache_dir':
                section['dir'] = self.optionPath(config[option], cfg_path)
            elif option == 'expiration_period':
                value = self.optionTimeval(config[option])
                section['expiration_period'] = value
            else:
                msg = "Unknown option: %s in section cache" % option
                raise ConfigError(msg)

    def sectionEnvironment(self, config, cfg_path):
        section = self.options['environment']

        config.pop('__name__', None)
        for option in config:
            if option == 'mac_pool_range':
                section['mac_pool_range'] = self.optionMacRange(config[option])
            elif option == 'rpcport':
                section['rpcport'] = self.optionPort(config[option])
            elif option == 'machine_pool_dirs':
                section['pool_dirs'] = self.optionDirList(config[option],
                                                           cfg_path)
            elif re.match(r'^machine_pool_dirs\s+\+$', option):
                section['pool_dirs'] += self.optionDirList(config[option],
                                                           cfg_path)
            elif option == 'test_module_dirs':
                section['module_dirs'] = self.optionDirList(config[option],
                                                           cfg_path)
            elif re.match(r'^test_module_dirs\s+\+$', option):
                section['module_dirs'] += self.optionDirList(config[option],
                                                           cfg_path)
            elif option == 'test_tool_dirs':
                section['tool_dirs'] = self.optionDirList(config[option],
                                                           cfg_path)
            elif re.match(r'^test_tool_dirs\s+\+$', option):
                section['tool_dirs'] += self.optionDirList(config[option],
                                                           cfg_path)
            else:
                msg = "Unknown option: %s in section environment" % option
                raise ConfigError(msg)

    def optionPort(self, option):
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

    def optionMacRange(self, option):
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

    def optionTimeval(self, option):
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
