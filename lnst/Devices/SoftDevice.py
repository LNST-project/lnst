"""
Defines the SoftDevice class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import pyroute2
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.DeviceError import DeviceError, DeviceConfigError
from lnst.Devices.Device import Device

class SoftDevice(Device):
    _name_template = "soft_dev"
    _link_type = ""

    #for common nl attributes - top level
    _link_map = {"name": "IFLA_IFNAME",
                 "hwaddr": "IFLA_ADDRESS",
                 "mtu": "IFLA_MTU"}

    #for link specific nl attributes - IFLA_LINKINFO level
    #should be specified by derived classes
    _linkinfo_data_map = {}

    def __init__(self, ifmanager, *args, **kwargs):
        super(SoftDevice, self).__init__(ifmanager)

        self._kwargs = kwargs

        if "name" not in self._kwargs:
            self._kwargs["name"] = ifmanager.assign_name(self._name_template)

    @property
    def name(self):
        try:
            return super(SoftDevice, self).name
        except:
            return self._kwargs["name"]

    def _parse_link(self, **kwargs):
        data = {}
        for key, nl_attr in self._link_map.items():
            if key in kwargs:
                data[nl_attr] = kwargs[key]
        return data

    def _parse_linkinfo(self, **kwargs):
        data = {"attrs": [("IFLA_INFO_KIND", self._link_type)]}
        data["attrs"].append(("IFLA_INFO_DATA",
                              self._parse_linkinfo_data(**kwargs)))
        return data

    def _parse_linkinfo_data(self, **kwargs):
        data = {"attrs": []}
        for key, nl_attr in self._linkinfo_data_map.items():
            if key in kwargs:
                data["attrs"].append((nl_attr, kwargs.pop(key)))
        return data

    def _generic_create_kwargs(self):
        kwargs = self._parse_link(**self._kwargs)
        kwargs["IFLA_LINKINFO"] = self._parse_linkinfo(**self._kwargs)
        return kwargs

    def _create(self):
        with pyroute2.IPRoute() as ipr:
            try:
                kwargs = self._generic_create_kwargs()
                ipr.link("add", **kwargs)
                self._if_manager.handle_netlink_msgs()
            except Exception as e:
                log_exc_traceback()
                raise DeviceConfigError("Creating link {} failed: {}".format(
                    self.name, str(e)))

    def destroy(self):
        with pyroute2.IPRoute() as ipr:
            try:
                ipr.link("del", index=self.ifindex)
                self._if_manager.rescan_devices()
            except Exception as e:
                log_exc_traceback()
                raise DeviceConfigError("Deleting link {} failed: {}".format(
                    self.name, str(e)))
        return True
