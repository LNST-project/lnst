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

from lnst.Devices.Device import Device
from lnst.Common.DeviceError import DeviceDeleted

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

        self._machine = None
        self.ifindex = None
        self.deleted = False
        self._inited = True

    def __deepcopy__(self, memo):
        newone = type(self)(self.__dev_cls,
                            list(self.__dev_args),
                            dict(self.__dev_kwargs))
        newone.__netns = self.__netns
        newone._machine = self._machine
        newone.ifindex = int(self.ifindex)
        newone.deleted = bool(self.deleted)
        newone._inited = bool(self._inited)
        return newone

    @property
    def _dev_cls(self):
        return self.__dev_cls

    @property
    def _dev_args(self):
        return self.__dev_args

    @property
    def _dev_kwargs(self):
        return self.__dev_kwargs

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

    def __getattr__(self, name):
        if name == "_inited":
            return False

        attr = getattr(self._dev_cls, name)

        if self.deleted:
            raise DeviceDeleted("This device was deleted on the slave and does not exist anymore.")

        if callable(attr):
            def dev_method(*args, **kwargs):
                return self._machine.rpc_call("dev_method", self.ifindex,
                                              name, args, kwargs,
                                              netns=self.netns.name)
            return dev_method
        else:
            return self._machine.rpc_call("dev_attr", self.ifindex, name,
                                          netns=self.netns.name)

    def __setattr__(self, name, value):
        if not self._inited:
            return super(RemoteDevice, self).__setattr__(name, value)

        try:
            getattr(self._dev_cls, name)
            return self._machine.rpc_call("dev_set_attr", self.ifindex, name, value,
                                          netns=self.netns.name)
        except AttributeError:
            return super(RemoteDevice, self).__setattr__(name, value)

    def __iter__(self):
        for x in dir(self._dev_cls):
            if x[0] == '_' or x[0:1] == "__":
                continue
            attr = getattr(self._dev_cls, x)

            if not callable(attr):
                yield (x, getattr(self, x))

    def _match_update_data(self, data):
        return False

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
