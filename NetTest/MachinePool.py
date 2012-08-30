"""
This module contains implementaion of MachinePool class that
can be used to maintain a cluster of test machines.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import os
import re
from Common.XmlProcessing import XmlDomTreeInit
from NetTestParse import MachineConfigParse

class MachinePool:
    """ This class is responsible for managing test machines
        that are available at controler and can be used for
        testing via template matching
    """

    _machines = {}

    def __init__(self, pool_dirs):
        for pool_dir in pool_dirs:
            self.add_dir(pool_dir)

    def add_dir(self, pool_dir):
        dentries = os.listdir(pool_dir)

        for dirent in dentries:
            self.add_file("%s/%s" % (pool_dir, dirent))

    def add_file(self, filepath):
        if os.path.isfile(filepath) and re.search("\.xml$", filepath, re.I):
            dom_init = XmlDomTreeInit()
            dom = dom_init.parse_file(filepath)

            dirname, basename = os.path.split(filepath)

            parser = MachineConfigParse()
            parser.set_include_root(dirname)
            parser.disable_events()

            machine = {"info": {}, "netdevices": {}}
            machine_id = re.sub("\.xml$", "", basename, flags=re.I)
            parser.set_machine(machine_id, machine)

            machineconfig = dom.getElementsByTagName("machineconfig")[0]
            parser.parse(machineconfig)
            self._machines[machine_id] = machine

    def get_machines(self):
        return self._machines

    def match_setup(self, templates):
        pass
