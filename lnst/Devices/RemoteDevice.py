"""
Defines the RemoteDevice class. This class wraps all other Device classes
when creating device instances on the Controller.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from copy import deepcopy
from lnst.Devices.Device import Device
from lnst.Common.DeviceError import DeviceDeleted, DeviceReadOnly

def remotedev_decorator(cls):
    def func(*args, **kwargs):
        return RemoteDevice(cls, args, kwargs)
    return func

class RemoteDevice(object):
    """Wraps all other Device classes on the Controller

    Ensures that all public methods of Device objects also act as the tester
    facing API even though the Device objects are instantiated on the Slave,
    not where the recipe script is actually running.
    """
    def __init__(self, dev_cls, args=[], kwargs={}):
        self.__dev_cls = dev_cls
        self.__dev_args = args
        self.__dev_kwargs = kwargs
        self.__netns = None
        self.__id = None

        self._machine = None
        self.ifindex = None
        self.deleted = False

        self._cache = {}
        self._cached = False

        self._inited = True

    def __deepcopy__(self, memo):
        newone = type(self)(self.__dev_cls,
                            deepcopy(self.__dev_args, memo),
                            deepcopy(self.__dev_kwargs, memo))
        newone.__netns = self.__netns
        newone._machine = self._machine
        newone.ifindex = deepcopy(self.ifindex, memo)
        newone.deleted = deepcopy(self.deleted, memo)
        newone._inited = deepcopy(self._inited, memo)
        return newone

    def enable_readonly_cache(self):
        self._cache = {}
        for name, val in self:
            self._cache[name] = val
        self._cached = True

    def disable_readonly_cache(self):
        self._cache = {}
        self._cached = False

    def update_readonly_cache(self):
        self.disable_readonly_cache()
        self.enable_readonly_cache()

    @property
    def _dev_cls(self):
        return self.__dev_cls

    @property
    def _dev_args(self):
        return self.__dev_args

    @property
    def _dev_kwargs(self):
        return self.__dev_kwargs

    def __id_get(self):
        return self.__id

    def __id_set(self, value):
        self.__id = value

    _id = property(__id_get, __id_set)

    def _get_dev_cls(self):
        return self._dev_cls

    @property
    def host(self):
        return self._machine._initns

    @property
    def netns(self):
        return self.__netns

    @netns.setter
    def netns(self, value):
        self.__netns = value

    def __dir__(self):
        return dir(self._dev_cls)

    def __getattr__(self, name):
        if name == "_inited":
            return False

        attr = getattr(self._dev_cls, name)

        if self.deleted and not self._cached:
            raise DeviceDeleted("This device was deleted on the slave and does not exist anymore.")

        if callable(attr):
            if self._cached:
                raise DeviceReadOnly("Can't call methods when in ReadOnly cache mode.")

            def dev_method(*args, **kwargs):
                return self._machine.remote_device_method(
                        self.ifindex, name, args, kwargs, self.netns)
            return dev_method
        else:
            if self._cached:
                return self._cache[name]

            return self._machine.remote_device_getattr(self.ifindex, name, self.netns)

    def __setattr__(self, name, value):
        if not self._inited:
            return super(RemoteDevice, self).__setattr__(name, value)

        try:
            getattr(self._dev_cls, name)
        except AttributeError:
            return super(RemoteDevice, self).__setattr__(name, value)

        if self._cached:
            raise DeviceReadOnly("Can't set attributes when in ReadOnly cache mode.")

        return self._machine.remote_device_setattr(self.ifindex, name, value, netns=self.netns)

    def __iter__(self):
        for x in dir(self._dev_cls):
            if x[0] == '_' or x[0:1] == "__":
                continue
            attr = getattr(self._dev_cls, x)

            if not callable(attr):
                yield (x, getattr(self, x))

    def _match_update_data(self, data):
        return False

    def __repr__(self):
        args = [
            "{}={}".format(k, v)
            for k, v in [
                ("machine", self._machine.get_id()),
                ("id", self._id),
                ("name", self.name),
                ("ifindex", self.ifindex),
            ]
        ]

        return "{}({})".format(self._dev_cls.__name__, ", ".join(args))

class PairedRemoteDevice(RemoteDevice):
    """RemoteDevice class for paired Devices (such as veth)"""
    def __init__(self, peer, dev_cls, args=[], kwargs={}):
        super(PairedRemoteDevice, self).__init__(dev_cls, args, kwargs)

        self._peer = peer

    @property
    def _dev_kwargs(self):
        ret = super(PairedRemoteDevice, self)._dev_kwargs
        ret["peer_if_id"] = self._peer.ifindex
        return ret

#register the RemoteDevice class as implementing the interface of the Device
#class - this is true because it just proxies method/attribute calls to the
#remote Slave where the correct method gets called.
#registering the RemoteDevice class as an implementation of the Device
#Interface is required for isinstance() checks in Common code -- Device is
#available on both Controller and Slave, but RemoteDevice only on Controller
Device.register(RemoteDevice)
