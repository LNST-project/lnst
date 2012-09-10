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
import logging
from ConfigParser import ConfigParser
from NetUtils import verify_ip_address, verify_mac_address

class ConfigError(Exception):
    pass

class Config():
    options = None
    _parser = None

    def __init__(self):
        self._parser = ConfigParser(dict_type=dict)
        self.options = dict()

    def get_config(self):
        return self.options

    def get_section(self, section):
        return self.options[section]

    def get_option(self, section, option):
        return self.options[section][option]

    def load_config(self, path):
        '''Parse and load the config file'''
        self._parser.read(path)

        sections = self._parser._sections
        for section in sections:
            if section == "log":
                self.sectionLogs(sections[section])
            elif section == "environment":
                self.sectionEnvironment(sections[section])
            else:
                msg = "Unknown section: %s" % section
                raise ConfigError(msg)

    def sectionLogs(self, config):
        if 'log' not in self.options:
            self.options['log'] = dict()
        section = self.options['log']

        config.pop('__name__', None)
        for option in config:
            if option == 'local_ip':
                section['local_ip'] = self.optionLocalIP(config[option])
            elif option == 'port':
                section['port'] = self.optionPort(config[option])
            elif option == 'path':
                section['path'] = self.optionLogPath(config[option])
            else:
                msg = "Unknown option: %s in section log" % option
                raise ConfigError(msg)

    def sectionEnvironment(self, config):
        if 'environment' not in self.options:
            self.options['environment'] = dict()
        section = self.options['environment']

        config.pop('__name__', None)
        for option in config:
            if option == 'mac_pool_range':
                section['mac_pool_range'] = self.optionMacRange(config[option])
            elif option == 'rpcport':
                section['rpcport'] = self.optionPort(config[option])
            else:
                msg = "Unknown option: %s in section environment" % option
                raise ConfigError(msg)

    def optionLocalIP(self, option):
        if not verify_ip_address(option):
            msg = "Invalid IP address: %s" % option
            raise ConfigError(msg)
        return option

    def optionPort(self, option):
        try:
            int(option)
        except ValueError:
            msg = "Option port expects a number."
            raise ConfigError(msg)
        return int(option)

    def optionLogPath(self, option):
        return option

    def optionMacRange(self, option):
        vals = option.split()
        if len(vals) != 2:
            msg = "Option mac_pool_range expects 2"\
                    " values sepparated by whitespaces."
            raise ConfigError(msg)
        if not verify_mac_address(option):
            msg = "Invalid MAC address: %s" % option
            raise ConfigError(msg)
        return vals
