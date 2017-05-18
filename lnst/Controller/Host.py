"""
Defines the Host class that acts as the tester facing API to manipulate and
work with remote machines running the LNST Slave.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
from lnst.Common.Parameters import Parameters
from lnst.Common.NetTestCommand import DEFAULT_TIMEOUT
from lnst.Devices import Devices
from lnst.Devices.VirtualDevice import VirtualDevice
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Controller.Common import ControllerError
from lnst.Controller.Job import Job

class HostError(ControllerError):
    pass

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

class Host(object):
    """Tester facing slave Host API

    Objects of this class are created by the Controller and provided to the
    Recipe object to use from it's 'test()' method. This tester facing API
    allows the tester to create new Devices and run Jobs on the remote Host.
    Example:
        m1.bond0 = Bond() # to create a new bond device
        m1.run("ip a") # to run a shell command
    """
    #TODO add packet capture options
    def __init__(self, host, **kwargs):
        self._host = host
        self.params = Parameters()
        self.params._from_dict(self._host._slave_desc)

        self.devices = Devices(self._host)
        self._device_mapping = {}

    def __getattr__(self, name):
        """direct access to Device objects

        All mapped devices of a Host are directly accessible as attributes of
        the Host objects. This is implemented by this __getattr__ override"""
        try:
            return self._device_mapping[name]
        except:
            raise AttributeError("%s object has no attribute named %r" %
                                 (self.__class__.__name__, name))

    def __setattr__(self, name, value):
        """allows for dynamic creation of devices

        During execution of the recipes 'test' method, a tester can create new
        soft devices by assigning a Device object to the Host object instance,
        this is implemented by overriding this __setattr__ method. It also
        handles VirtualDevice creation before recipe execution (virtual match).
        """
        if isinstance(value, VirtualDevice):
            # TODO creation of VirtualDevices should be disabled during test
            # execution, it's commented out right now because I haven't found
            # a good solution yet...
            # msg = "Creating VirtualDevices in recipe execution is "\
                  # "not supported right now."
            # raise HostError(msg)
            if name in self._device_mapping:
                raise HostError("Device with name '%s' already assigned." % name)

            value.host = self._host
            self._host.add_tmp_device(value)
            value.create()
            self._host.wait_for_tmp_devices(DEFAULT_TIMEOUT)

            self._device_mapping[name] = value
        elif isinstance(value, RemoteDevice):
            if name in self._device_mapping:
                raise HostError("Device with name '%s' already assigned." % name)

            if value.if_index is None:
                value.host = self._host
                self._host.create_remote_device(value)
            self._device_mapping[name] = value
        else:
            super(Host, self).__setattr__(name, value)

    def _map_device(self, dev_id, how):
        hwaddr = how["hwaddr"]
        dev = self._host.get_dev_by_hwaddr(hwaddr)
        self._device_mapping[dev_id] = dev

    def run(self, what, bg=False, fail=False, timeout=DEFAULT_TIMEOUT,
            json=False, netns=None, desc=None):
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
            netns: Run in the specified network namespace. Currently not
                functional.
            desc: Decription printed in logs. Accepts a string value.

        Returns:
            a Job object that acts as a handle to access the remote Job. If
            the Job was ran on foreground, the returned Job object will be
            filled with result data. If the Job was ran in background, the
            immediately returned Job object can be used to manipulate the
            running Job remotely and when the result data arrives from the Slave
            the Job object will be automatically updated.
        """
        #TODO support network namespaces
        if netns is not None:
            raise HostError("netns parameter not supported yet.")

        job = Job(self._host, what, expect=not fail, json=json, netns=netns,
                  desc=desc)

        try:
            self._host.run_job(job)

            if not bg:
                if not job.wait(timeout):
                    logging.debug("Killing timed-out job")
                    job.kill()
        except:
            raise
        finally:
            pass
            #TODO check expect result here
            # if bg=True:
            #     add "job started" result
            # else:
            #     add job result

        return job
