"""
Defines the SoftDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceConfigError
from lnst.Devices.Device import Device

class SoftDevice(Device):
    _name_template = "soft_dev"
    _link_type = ""
    _linkinfo_prefix = ""

    _mandatory_opts = []

    def __init__(self, ifmanager, **kwargs):
        super(SoftDevice, self).__init__(ifmanager)

        self._bulk_enabled = True

        if "name" not in kwargs:
            kwargs["name"] = ifmanager.assign_name(self._name_template)

        self._orig_name = kwargs["name"]

        for i in self._mandatory_opts:
            if i not in kwargs:
                raise DeviceConfigError("Option {} is mandatory for type {}".
                        format(i, self.__class__.__name__))

        for k, v in kwargs.items():
            setattr(self, k, v)

    @Device.name.getter
    def name(self):
        try:
            return super(SoftDevice, self).name
        except:
            return self._orig_name

    def _set_linkinfo_data_attr(self, attr, val):
        self._update_attr(self._link_type, "IFLA_LINKINFO", "IFLA_INFO_KIND")
        self._update_attr(val, "IFLA_LINKINFO", "IFLA_INFO_DATA", attr)

    def _get_linkinfo_data_attr(self, attr_name):
        return self._nl_msg.get_nested("IFLA_LINKINFO", "IFLA_INFO_DATA",
                                       attr_name)

    def _create(self):
        self._update_attr(self._link_type, "IFLA_LINKINFO", "IFLA_INFO_KIND")
        try:
            self._nl_link_sync("add", bulk=True)
        except Exception as e:
            log_exc_traceback()
            raise DeviceConfigError("Creating link {} failed: {}".format(
                self.name, str(e)))

    def destroy(self):
        self._ipr_wrapper("link", "del", index=self.ifindex)
        return True
