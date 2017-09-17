"""
Defines the Host class that represents the API for the root namespace of a
slave machine.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Common.Parameters import Parameters
from lnst.Controller.Namespace import Namespace
from lnst.Controller.NetNamespace import NetNamespace

class Hosts(object):
    """Container object for Host class instances

    Implements the __iter__ method to allow iterating Host objects. Created
    automatically by the LNST Controller class and provided to the tester
    in the test() method of a BaseRecipe class as the 'matched' attribute.
    """
    def __iter__(self):
        for x in dir(self):
            val = getattr(self, x)
            if isinstance(val, Host):
                yield val

class Host(Namespace):
    """Namespace derived class for the root namespace

    Should not be created by the tester, instead it's automatically created
    by the LNST Controller before the 'test' method of a recipe is called.

    In addition to the base Namespace class it allows for assignment of a
    NetNamespace instance to create a new network namespace on the host."""
    def __init__(self, host, **kwargs):
        super(Host, self).__init__(host)
        self.params = Parameters()
        self.params._from_dict(self._host._slave_desc)

        self._host.set_root_ns(self)

    @property
    def namespaces(self):
        """List of network namespaces available on the machine

        Does not include the root namespace (self)."""
        ret = []
        for x in self._host._objects.values():
            if isinstance(x, NetNamespace):
                ret.append(x)
        return ret

    def _map_device(self, dev_id, how):
        hwaddr = how["hwaddr"]
        dev = self._host.get_dev_by_hwaddr(hwaddr)
        self._objects[dev_id] = dev
        dev._enable()

    def _custom_setattr(self, name, value):
        if not super(Host, self)._custom_setattr(name, value):
            if isinstance(value, NetNamespace):
                self._host.add_netns(value.nsname)
                self._objects[name] = value
                value._host = self._host
                return True
            else:
                return False
        else:
            return True
