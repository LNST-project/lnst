"""
Defines the MessageDispatcher class used by the Controller to multiplex
communication from all the connected Slave machines.

In addition to that it defines functions used by the MessageDispatcher to
transparently translate Device objects while communicating with the Slave.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
import copy
from lnst.Common.ConnectionHandler import send_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Parameters import Parameters, DeviceParam
from lnst.Common.DeviceRef import DeviceRef
from lnst.Controller.Common import ControllerError
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Tests.BaseTestModule import BaseTestModule

def deviceref_to_remote_device(machine, obj):
    if isinstance(obj, DeviceRef):
        dev = machine.dev_db_get_ifindex(obj.ifindex)
        return dev
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            new_dict[key] = deviceref_to_remote_device(machine,
                                                       value)
        return new_dict
    elif isinstance(obj, list):
        new_list = []
        for value in obj:
            new_list.append(deviceref_to_remote_device(machine,
                                                       value))
        return new_list
    elif isinstance(obj, tuple):
        new_list = []
        for value in obj:
            new_list.append(deviceref_to_remote_device(machine,
                                                       value))
        return tuple(new_list)
    else:
        return obj

def remote_device_to_deviceref(obj):
    if isinstance(obj, RemoteDevice):
        return DeviceRef(obj.ifindex)
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            new_dict[key] = remote_device_to_deviceref(value)
        return new_dict
    elif isinstance(obj, list):
        new_list = []
        for value in obj:
            new_list.append(remote_device_to_deviceref(value))
        return new_list
    elif isinstance(obj, tuple):
        new_list = []
        for value in obj:
            new_list.append(remote_device_to_deviceref(value))
        return tuple(new_list)
    elif isinstance(obj, Parameters):
        for param_name, param in obj:
            setattr(obj, param_name, remote_device_to_deviceref(param))
        return obj
    elif isinstance(obj, BaseTestModule):
        new_test = copy.deepcopy(obj)
        new_test.params = remote_device_to_deviceref(new_test.params)
        return new_test
    else:
        return obj

class ConnectionError(ControllerError):
    pass

class MessageDispatcher(ConnectionHandler):
    def __init__(self, log_ctl):
        super(MessageDispatcher, self).__init__()
        self._log_ctl = log_ctl
        self._machines = dict()

    def add_slave(self, machine, connection):
        self._machines[machine] = machine
        self.add_connection(machine, connection)

    def send_message(self, machine, data):
        soc = self.get_connection(machine)
        data = remote_device_to_deviceref(data)

        if send_data(soc, data) == False:
            msg = "Connection error from slave %s" % machine.get_id()
            raise ConnectionError(msg)

        result = None
        while True:
            connected_slaves = self._connection_mapping.keys()

            messages = self.check_connections()

            remaining_slaves = self._connection_mapping.keys()

            for msg in messages:
                if msg[1]["type"] == "result" and msg[0] == machine:
                    if result is not None:
                        msg = ("Multiple result messages from the same slave "
                               "'{}'".format(machine.get_id()))
                        raise ConnectionError(msg)
                    result = msg[1]
                else:
                    self._process_message(msg)

            if connected_slaves != remaining_slaves:
                disconnected_slaves = set(connected_slaves) -\
                                      set(remaining_slaves)
                msg = "Slaves " + str(list(disconnected_slaves)) + \
                      " disconnected from the controller."
                raise ConnectionError(msg)

            if result is not None:
                return deviceref_to_remote_device(machine, result["result"])

    def wait_for_job_finish(self, job):
        def condition_check():
            return job.finished
        self.wait_for_condition(condition_check)
        return True

    def wait_for_condition(self, condition_check):
        wait = True
        while wait:
            connected_slaves = self._connection_mapping.keys()

            messages = self.check_connections(timeout=1)

            remaining_slaves = self._connection_mapping.keys()

            for msg in messages:
                self._process_message(msg)
                wait = wait and not condition_check()

            wait = wait and not condition_check()

            if connected_slaves != remaining_slaves:
                disconnected_slaves = set(connected_slaves) -\
                                      set(remaining_slaves)
                msg = "Slaves " + str(list(disconnected_slaves)) + \
                      " disconnected from the controller."
                raise ConnectionError(msg)
        return True

    def handle_messages(self):
        connected_slaves = self._connection_mapping.keys()

        messages = self.check_connections()

        remaining_slaves = self._connection_mapping.keys()

        for msg in messages:
            self._process_message(msg)

        if connected_slaves != remaining_slaves:
            disconnected_slaves = set(connected_slaves) -\
                                  set(remaining_slaves)
            msg = "Slaves " + str(list(disconnected_slaves)) + \
                  " disconnected from the controller."
            raise ConnectionError(msg)
        return True

    def _process_message(self, message):
        if message[1]["type"] == "log":
            record = message[1]["record"]
            self._log_ctl.add_client_log(message[0].get_id(), record)
        elif message[1]["type"] == "result":
            msg = "Recieved result message from different slave %s" % message[0].get_id()
            logging.debug(msg)
        elif message[1]["type"] == "dev_created":
            machine = self._machines[message[0]]
            machine.device_created(message[1]["dev_data"])
        elif message[1]["type"] == "dev_deleted":
            machine = self._machines[message[0]]
            machine.device_delete(message[1])
        elif message[1]["type"] == "exception":
            raise message[1]["Exception"]
        elif message[1]["type"] == "job_finished":
            machine = self._machines[message[0]]
            machine.job_finished(message[1])
        else:
            msg = "Unknown message type: %s" % message[1]["type"]
            raise ConnectionError(msg)

    def disconnect_slave(self, machine):
        soc = self.get_connection(machine)
        self.remove_connection(soc)
        del self._machines[machine]
