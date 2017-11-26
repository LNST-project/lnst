"""
Defines the TeamDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.Utils import bool_it
from lnst.Devices.MasterDevice import MasterDevice

def prepare_json_str(json_str):
    if not json_str:
        return "{}"
    json_str = json_str.replace('"', '\\"')
    json_str = re.sub('\s+', ' ', json_str)
    return json_str

#TODO rework with pyroute2? don't know how json and teamd works with that...
class TeamDevice(MasterDevice):
    _name_template = "t_team"

    def __init__(self, ifmanager, *args, **kwargs):
        super(TeamDevice, self).__init__(ifmanager, *args, **kwargs)

        self._config = kwargs.get("config", None)
        self._dbus = not bool_it(kwargs.get("disable_dbus", False))

    @property
    def config(self):
        return self._config

    @property
    def dbus(self):
        return self._dbus

    def _create(self):
        teamd_config = prepare_json_str(self.config)

        exec_cmd("teamd -r -d -c \"%s\" -t %s %s" %\
                    (teamd_config,
                     self.name,
                     " -D" if self.dbus else ""))

        retry = 0
        while self._nl_msg is None and retry < 5:
            retry += 1
            self._if_manager.rescan_devices()

    def destroy(self):
        exec_cmd("teamd -k -t %s" % self.name)

    def slave_add(self, dev, port_config=None):
        exec_cmd("teamdctl %s %s port config update %s \"%s\"" %\
                    (" -D" if self.dbus else "",
                     self.name,
                     dev.name,
                     prepare_json_str(port_config)))

        dev.master = self
