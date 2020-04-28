"""
Defines the TeamDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""
import json
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.MasterDevice import MasterDevice


# TODO Rework with pyroute2 if thats possible.
# See https://github.com/svinota/pyroute2/issues/699#issuecomment-615367686
class TeamDevice(MasterDevice):
    _name_template = "t_team"

    def __init__(self, ifmanager, *args, **kwargs):
        self._config = {}
        self._dbus = False
        super(TeamDevice, self).__init__(ifmanager, *args, **kwargs)

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, v: dict):
        if not isinstance(v, dict):
            raise DeviceConfigError("team device config must be dict")
        self._config = v

    @property
    def dbus(self):
        return self._dbus

    @dbus.setter
    def dbus(self, v: bool):
        if not isinstance(v, bool):
            raise DeviceConfigError("team dbus setting must be bool")
        self._dbus = v

    def _create(self):
        teamd_json = json.dumps(self.config)
        cmd = f"teamd -r -d -c '{teamd_json}' -t {self.name}"
        if self.dbus:
            cmd += " -D"
        exec_cmd(cmd)

        retry = 0
        while self._nl_msg is None and retry < 5:
            retry += 1
            self._if_manager.rescan_devices()

    def destroy(self):
        exec_cmd("teamd -k -t %s" % self.name)

    def slave_add(self, dev, port_config={}):
        if not isinstance(port_config, dict):
            raise DeviceConfigError(f"team link {dev.name} port config must be dict")

        port_json = json.dumps(port_config)
        opts = "-D" if self.dbus else ""
        exec_cmd(f"teamdctl {opts} {self.name} port config "
                 f"update {dev.name} '{port_json}'")

        dev.master = self
