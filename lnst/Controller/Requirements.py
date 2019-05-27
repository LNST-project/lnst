"""
This module defines the DeviceReq and HostReq classes, which can be used to
create a global description of Requirements for a network test. You can use
these to define class attributes of a BaseRecipe derived class to specify
"general" requirements for that Recipe, or you can add them to an instance of a
Recipe derived class based on it's parameters to define requirements "specific"
for that single test run.

The module also specifies a Requirements class which serves as a container for
HostReq objects, while HostReq classes also serve as containers for DeviceReq
objects. The object tree created this way is translated to a dictionary used by
the internal LNST matching algorithm against available machines.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import copy
from lnst.Common.LnstError import LnstError
from lnst.Common.Parameters import Parameters, Param

class RequirementError(LnstError):
    pass

class RecipeParam(Param):
    def __init__(self, name, mandatory=False, **kwargs):
        self.name = name
        super(RecipeParam, self).__init__(mandatory, **kwargs)

class BaseReq(object):
    def __init__(self, **kwargs):
        self.params = Parameters()
        for name, val in list(kwargs.items()):
            if name == "params":
                raise RequirementError("'params' is a reserved keyword.")
            setattr(self.params, name, val)

    def reinit_with_params(self, recipe_params):
        for name, val in self.params:
            if isinstance(val, RecipeParam):
                if val.name in recipe_params:
                    new_val = getattr(recipe_params, val.name)
                    setattr(self.params, name, new_val)
                else:
                    try:
                        new_val = copy.deepcopy(val.default)
                        setattr(self.params, name, new_val)
                    except AttributeError:
                        if val.mandatory:
                            raise RequirementError(
                                    "Recipe parameter {} is mandatory for Recipe Requirements parameter {}"
                                    .format(val.name, name))
                        else:
                            delattr(self.params, name)

class HostReq(BaseReq):
    """Specifies a Slave machine requirement

    To define a Host requirement you assign a HostReq instance to a class
    attribute of a BaseRecipe derived class.
    Example:
    class MyRecipe(BaseRecipe):
        m1 = HostReq()

    Args:
        kwargs -- any other arguments will be treated as arbitrary string
            parameters that will be matched to parameters of Slave machines
            which can define their parameter values based on the implementation
            of the SlaveMachineParser
    """
    def reinit_with_params(self, recipe_params):
        super(HostReq, self).reinit_with_params(recipe_params)

        for name, dev_req in self:
            dev_req.reinit_with_params(recipe_params)

    def __iter__(self):
        for x in dir(self):
            val = getattr(self, x)
            if isinstance(val, DeviceReq):
                yield (x, val)

    def _to_dict(self):
        res = {'interfaces': {}, 'params': {}}
        for dev_id, dev in self:
            res['interfaces'][dev_id] = dev._to_dict()
        res['params'] = self.params._to_dict()
        return res

class DeviceReq(BaseReq):
    """Specifies an Ethernet Device requirement

    To define a Device requirement you assign a DeviceReq instance to a HostReq
    instance in a BaseRecipe derived class.
    Example:
    class MyRecipe(BaseRecipe):
        m1 = HostReq()
        m1.eth0 = DeviceReq(label="net1")

    Args:
        label -- string value indicating the network the Device is connected to
        kwargs -- any other arguments will be treated as arbitrary string
            parameters that will be matched to parameters of Slave machines
            which can define their parameter values based on the implementation
            of the SlaveMachineParser
    """
    def __init__(self, label, **kwargs):
        self.label = label
        super(DeviceReq, self).__init__(**kwargs)

    def _to_dict(self):
        res = {'network': self.label,
               'params': self.params._to_dict()}
        return res

class _Requirements(object):
    """Hosts a copy of requirements for a Recipe instance

    Internally used class.
    """
    def _to_dict(self):
        res = {}
        for h_id, host in self:
            res[h_id] = host._to_dict()
        return res

    def __iter__(self):
        for x in dir(self):
            val = getattr(self, x)
            if isinstance(val, HostReq):
                yield (x, val)
