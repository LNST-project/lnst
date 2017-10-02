"""
This module defines the Param class, it's type specific derivatives
(IntParam, StrParam) and the Parameters class which serves as a container for
Param instances. This can be used by a BaseRecipe class to specify
optional/mandatory parameters for the entire test, or by HostReq and DeviceReq
classes to define specific parameters needed for the matching algorithm.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import copy
from lnst.Common.DeviceRef import DeviceRef
from lnst.Common.IpAddress import ipaddress
from lnst.Common.LnstError import LnstError

class ParamError(LnstError):
    pass

class Param(object):
    def __init__(self, mandatory=False, **kwargs):
        self.mandatory = mandatory
        if "default" in kwargs:
            self.default = kwargs["default"]

    def type_check(self, value):
        return value

class IntParam(Param):
    def type_check(self, value):
        try:
            return int(value)
        except ValueError:
            raise ParamError("Value must be a valid integer")

class FloatParam(Param):
    def type_check(self, value):
        try:
            return float(value)
        except ValueError:
            raise ParamError("Value must be a valid float")

class StrParam(Param):
    def type_check(self, value):
        try:
            return str(value)
        except ValueError:
            raise ParamError("Value must be a string")

class IpParam(Param):
    def type_check(self, value):
        try:
            return ipaddress(value)
        except ValueError:
            raise ParamError("Value must be a BaseIpAddress, string ip address or a Device object. Not {}"
                             .format(type(value)))

class DeviceParam(Param):
    def type_check(self, value):
        #runtime import this because the Device class arrives on the Slave
        #during recipe execution, not during Slave init
        from lnst.Devices.Device import Device
        if isinstance(value, Device) or isinstance(value, DeviceRef):
            return value
        else:
            raise ParamError("Value must be a Device or DeviceRef object."
                             " Not {}".format(type(value)))

class Parameters(object):
    def __init__(self):
        self._attrs = {}

    def __getattr__(self, name):
        if name == "_attrs":
            return object.__getattribute__(self, name)

        try:
            return self._attrs[name]
        except KeyError:
            return object.__getattribute__(self, name)

    def __setattr__(self, name, val):
        if name == "_attrs":
            super(Parameters, self).__setattr__(name, val)
        else:
            self._attrs[name] = val

    def __contains__(self, name):
        return name in self._attrs

    def __iter__(self):
        for attr, val in self._attrs.items():
            yield (attr, val)

    def _to_dict(self):
        return copy.deepcopy(self._attrs)

    def _from_dict(self, d):
        for name, val in d.items():
            setattr(self, name, copy.deepcopy(val))

    def __str__(self):
        result = ""
        for attr, val in self._attrs.items():
            result += "%s = %s\n" % (attr, str(val))
        return result
