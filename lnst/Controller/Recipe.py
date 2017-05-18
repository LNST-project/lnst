"""
Module implementing the BaseRecipe class.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import copy
from lnst.Common.Parameters import Parameters, Param
from lnst.Controller.Requirements import _Requirements, HostReq
from lnst.Controller.Common import ControllerError

class RecipeError(ControllerError):
    """Exception thrown by the BaseRecipe class"""
    pass

class BaseRecipe(object):
    """BaseRecipe class

    Every LNST Recipe written by testers should be inherited from this class.
    An LNST Recipe is composed of several parts:
    * Requirements definition - you define recipe requirements in a derived
        class by defining class attributes of the HostReq type. You can further
        specify Ethernet Device requirements by defining DeviceReq attributes
        of the HostReq object.
        Example:
        m1 = HostReq(arch="x86_64")
        m1.eth0 = DeviceReq(hwaddr="52:54:00:12:34:56")
    * Parameter definition (optional) - you can define paramaters of you Recipe
        by defining class attributes of the Param type (or inherited). These
        parameters can then be accessed from the test() method to change it's
        behaviour. Parameter validity (type) is checked during the
        instantiation of the Recipe object by the base __init__ method.
        You can define your own __init__ method to implement more complex
        Parameter checking if needed, but you MUST call the base __init__
        method first.
    * Test definition - this is done by defining the test() method, in this
        method the tester has direct access to mapped LNST slave Hosts, can
        manipulate them and implement his tests.

    Attributes:
        matched -- when running the Recipe the Controller will fill this
            attribute with a Hosts object after the Mapper finds suitable slave
            hosts.
        req -- instantiated Requirements object, you can optionally change the
            Recipe requirements through this object during runtime (e.g.
            variable number of hosts or devices of a host based on a Parameter)
        params -- instantiated Parameters object, can be used to access the
            calculated parameters during Recipe initialization/execution
    """
    def __init__(self, **kwargs):
        """
        The __init__ method does 2 things:
        * copies Requirements -- since Requirements are defined as class
            attributes, we need to copy the objects to avoid conflicts with
            multiple instances of the same class etc...
            The copied objects are stored under a Requirements object available
            through the 'req' attribute. This way you can optionally change the
            Requirements of an instantiated Recipe.
        * copies and instantiates Parameters -- Parameters are also class
            attributes so they need to be copied into a Parameters() object
            (accessible in the 'params' attribute).
            Next, the copied objects are loaded with values from kwargs
            and checked if mandatory Parameters have values.
        """
        self.matched = None
        self.req = _Requirements()
        self.params = Parameters()
        for attr in dir(self):
            val = getattr(self, attr)
            if isinstance(val, HostReq):
                setattr(self.req, attr, copy.deepcopy(val))
            elif isinstance(val, Param):
                setattr(self.params, attr, copy.deepcopy(val))

        for name, val in kwargs.items():
            try:
                param = getattr(self.params, name)
                param.val = val
            except:
                raise RecipeError("Unknown parameter {}".format(name))

        for name, param in self.params:
            if param.mandatory and not param.set:
                raise RecipeError("Parameter {} is mandatory".format(name))

    def _set_hosts(self, hosts):
        self.matched = hosts

    def test(self):
        """Method to be implemented by the Tester"""
        raise NotImplementedError("Method test must be defined by a child class.")
