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

from lnst.Common.IpAddress import BaseIpAddress, IpAddress
from lnst.Common.LnstError import LnstError

class ParamError(LnstError):
    pass

class Param(object):
    def __init__(self, mandatory=False, default=None):
        self.mandatory = mandatory
        self.default = default
        self._val = None
        self.set = False
        if self.default:
            self.val = self.default

    @property
    def val(self):
        return self._val

    @val.setter
    def val(self, value):
        self._val = value
        self.set = True

    def __str__(self):
        return str(self.val)

class IntParam(Param):
    @Param.val.setter
    def val(self, value):
        try:
            self._val = int(value)
        except:
            raise ParamError("Value must be a valid integer")
        self.set = True

    def __int__(self):
        return self.val

class FloatParam(Param):
    @Param.val.setter
    def val(self, value):
        try:
            self._val = float(value)
        except:
            raise ParamError("Value must be a valid float")
        self.set = True

    def __float__(self):
        return self.val

class StrParam(Param):
    @Param.val.setter
    def val(self, value):
        try:
            self._val = str(value)
        except:
            raise ParamError("Value must be a string")
        self.set = True

class IpParam(Param):
    @Param.val.setter
    def val(self, value):
        if isinstance(value, BaseIpAddress):
            self._val = value
        elif isinstance(value, str):
            self._val = IpAddress(value)
        else:
            raise ParamError("Value must be a BaseIpAddress or string object."
                             "Not {}".format(type(value)))
        self.set = True

class Parameters(object):
    def __getattribute__(self, name):
        """
        Overriding the default __getattribute__ method is important for being
        able to deepcopy a Parameters object while also allowing to return None
        for undefined Parameter names. This is because the copy module relies
        on an exception being raised for certain private attributes and
        returning None would break it.
        """
        if name[:2] == "__" or name[:1] == "_":
            return object.__getattribute__(self, name)

        try:
            return object.__getattribute__(self, name)
        except:
            return None

    def __iter__(self):
        for attr in dir(self):
            val = getattr(self, attr)
            if isinstance(val, Param):
                yield (attr, val)

    def _to_dict(self):
        res = {}
        for name, param in self:
            res[name] = str(param.val)
        return res

    def _from_dict(self, d):
        for name, val in d.items():
            if isinstance(val, Param):
                setattr(self, name, val)
            else:
                new_param = StrParam()
                new_param.val = val
                setattr(self, name, new_param)

    def __str__(self):
        result = ""
        for attr in dir(self):
            val = getattr(self, attr)
            if isinstance(val, Param):
                result += "%s = %s\n" % (attr, str(val))
        return result
