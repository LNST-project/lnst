"""
TODO

Copyright 2018 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

class AgentProxyObject(object):
    def __init__(self, machine, cls, obj_ref):
        self._inited = False
        self.__cls = cls
        self.__obj_ref = obj_ref
        self.__machine = machine

        self._inited = True

    def __getattr__(self, name):
        if name == "_inited":
            return super(AgentProxyObject, self).__getattribute__(name)

        if not self._inited:
            return super(AgentProxyObject, self).__getattr__(name)

        attr = getattr(self.__cls, name)

        if callable(attr):
            def obj_method(*args, **kwargs):
                return self.__machine.rpc_call("obj_method", self.__obj_ref,
                                               name, args, kwargs)
            return obj_method
        else:
            return self.__machine.rpc_call("obj_getattr", self.__obj_ref, name)

    def __setattr__(self, name, value):
        if name == "_inited" or not self._inited:
            return super(AgentProxyObject, self).__setattr__(name, value)

        return self.__machine.rpc_call("obj_setattr", self.__obj_ref, name,
                                      value)
