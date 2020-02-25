"""
Defines the abstract class Namespace that represents the base of both the
Host (init namespace) and NetNamespace (other network namespaces) classes. It
defines the tester facing APIs which should be mostly identical for both, with
slight differences. The Namespace class should never be instantiated on it's
own, only the derived classes should be created.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from abc import ABCMeta
from lnst.Controller.Job import DEFAULT_TIMEOUT
from lnst.Devices.Device import Device
from lnst.Devices.VirtualDevice import VirtualDevice
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Controller.Common import ControllerError
from lnst.Controller.Job import Job
from lnst.Controller.RecipeResults import ResultLevel

class HostError(ControllerError):
    pass

class Namespace(object):
    """Tester facing slave API

    Objects of this class are created by the Controller and provided to the
    Recipe object to use from it's 'test()' method. This tester facing API
    allows the tester to create new Devices and run Jobs on the remote Host.
    Example:
        m1.bond0 = Bond() # to create a new bond device
        m1.run("ip a") # to run a shell command"""

    #TODO add packet capture options
    def __init__(self, machine):
        #storage for mapped objects (Devices, Namespaces...)
        self._objects = {}
        self._name = None

        self._machine = machine
        self.jobs = None #TODO

    @property
    def initns(self):
        return self._machine._initns

    @property
    def hostid(self):
        return self._machine.get_id()

    @property
    def hostname(self):
        return self._machine.get_hostname()

    @property
    def devices(self):
        """List of mapped devices available in the Namespace"""
        ret = []
        for x in list(self._objects.values()):
            if isinstance(x, Device) and x.netns == self:
                ret.append(x)
        return ret

    @property
    def device_database(self):
        """List of all devices (including unmapped) available in the Namespace"""
        ret = []
        for x in list(self._machine._device_database.values()):
            if isinstance(x, Device) and x.netns == self:
                ret.append(x)
        return ret

    @property
    def name(self):
        """The name of the Namespace

        returns None for the init namespace
        returns a string name for any other namespace"""
        return self._name

    def prepare_job(self, what, fail=False, json=False, desc=None,
                    job_level=ResultLevel.DEBUG):
        return Job(self, what, expect=not fail, json=json, desc=desc,
                   level=job_level)

    def run(self, what, fail=False, json=False, desc=None,
            job_level=ResultLevel.IMPORTANT, bg=False, timeout=DEFAULT_TIMEOUT):
        """
        Args:
            what (mandatory) -- what should be run on the host. Can be either a
                string, that will be executed on the Host as a shell command,
                or a TestModule object.
            bg --  run in background flag. Default 'False'. When True, the
                method will return immediately after the Job request is sent
                to the Slave Host.
            fail -- default 'False'. If True, a Failure will be reported as PASS
            timeout: time limit in seconds. Default is 60. Only respected for
                jobs running in foreground (background Jobs don't have a time
                limit)
            json: Process JSON output into dictionary. Default 'False'.
            desc: Decription printed in logs. Accepts a string value.

        Returns:
            a Job object that acts as a handle to access the remote Job. If
            the Job was ran on foreground, the returned Job object will be
            filled with result data. If the Job was ran in background, the
            immediately returned Job object can be used to manipulate the
            running Job remotely and when the result data arrives from the Slave
            the Job object will be automatically updated.
        """
        job = self.prepare_job(what, fail, json, desc, job_level)
        job.start(bg, timeout)
        return job

    def __getattr__(self, name):
        """direct access to Device objects

        All mapped devices of a Host are directly accessible as attributes of
        the Host objects. This is implemented by this __getattr__ override"""
        try:
            return self._objects[name]
        except:
            raise AttributeError("%s object has no attribute named %r" %
                                 (self.__class__.__name__, name))

    def _custom_setattr(self, name, value):
        #when self._objects doesn't exist yet (in __init__) there's nothing to
        #do
        try:
            self._objects
        except:
            return False

        try:
            if name in self._objects or getattr(self, name) is not None:
                raise HostError("Name '%s' already assigned." % name)
        except AttributeError:
            pass

        if isinstance(value, RemoteDevice):
            if value.ifindex is not None:
                if value.netns is self:
                    if name not in self._objects:
                        self._objects[name] = value
                    elif self._objects[name] is not value:
                        raise HostError("Different object with same name is already assined")
                    return True
                old_ns = value.netns
                old_ns._unset(value)
                self._machine.remote_device_set_netns(value, self, old_ns)
                value.netns = self
                self._objects[name] = value
                return True
            else:
                value._id = name
                if isinstance(value, VirtualDevice):
                    # TODO creation of VirtualDevices should be disabled during
                    # test execution, it's commented out right now because I
                    # haven't found a good solution yet...
                    # msg = "Creating VirtualDevices in recipe execution is "\
                          # "not supported right now."
                    # raise HostError(msg)
                    if self.name is not None:
                        raise HostError("Can't create VirtualDevice in a netns")

                    value._machine = self._machine
                    value.netns = self
                    self._machine.add_tmp_device(value)
                    value._create()
                    self._machine.wait_for_tmp_devices(DEFAULT_TIMEOUT)
                else:
                    value._machine = self._machine
                    value.netns = self
                    self._machine.remote_device_create(value, netns=self)

            self._objects[name] = value
            return True
        else:
            return False

    def __setattr__(self, name, value):
        """allows for dynamic creation of devices

        During execution of the recipes 'test' method, a tester can create new
        soft devices by assigning a Device object to the Namespace object
        instance, this is implemented by overriding this __setattr__ method. It
        also handles VirtualDevice creation before recipe execution (virtual
        match).
        """
        if not self._custom_setattr(name, value):
            super(Namespace, self).__setattr__(name, value)

    def __delattr__(self, name):
        if name in self._objects and isinstance(self._objects[name], RemoteDevice):
            if self._objects[name].deleted:
                del self._objects[name]
        else:
            super(Namespace, self).__delattr__(name)

    def _unset(self, value):
        k_to_del = None
        for k, v in list(self._objects.items()):
            if v == value:
                k_to_del = k
                break

        if k_to_del:
            del self._objects[k_to_del]
            return True
        else:
            return False

    def __str__(self):
        return "{cls}(machine_id={m_id}{namespace})".format(
            cls=self.__class__.__name__,
            m_id=self._machine.get_id(),
            namespace=", namespace_name={}".format(self.name) if self.name else "",
        )
