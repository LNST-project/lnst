"""
Defines the MessageDispatcher class used by the Controller to multiplex
communication from all the connected Agent machines.

In addition to that it defines functions used by the MessageDispatcher to
transparently translate Device objects while communicating with the Agent.

Copyright 2017 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import logging
import copy
import signal
from lnst.Common.ConnectionHandler import send_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Parameters import Parameters
from lnst.Common.DeviceRef import DeviceRef
from lnst.Controller.Common import ControllerError
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Tests.BaseTestModule import BaseTestModule

def deviceref_to_remote_device(machine, obj, netns):
    if isinstance(obj, DeviceRef):
        dev = machine.dev_db_get_ifindex(obj.ifindex, netns)
        return dev
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in list(obj.items()):
            new_dict[key] = deviceref_to_remote_device(machine,
                                                       value,
                                                       netns)
        return new_dict
    elif isinstance(obj, list):
        new_list = []
        for value in obj:
            new_list.append(deviceref_to_remote_device(machine,
                                                       value,
                                                       netns))
        return new_list
    elif isinstance(obj, tuple):
        new_list = []
        for value in obj:
            new_list.append(deviceref_to_remote_device(machine,
                                                       value,
                                                       netns))
        return tuple(new_list)
    else:
        return obj

def remote_device_to_deviceref(obj):
    if isinstance(obj, RemoteDevice):
        return DeviceRef(obj.ifindex)
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in list(obj.items()):
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
        new_test._orig_kwargs = remote_device_to_deviceref(new_test._orig_kwargs)
        return new_test
    else:
        return obj

class ConnectionError(ControllerError):
    pass

class WaitTimeoutError(ControllerError):
    pass

def _timeout_handler(signum, frame):
    msg = "Timeout expired"
    raise WaitTimeoutError(msg)

class MessageDispatcher(ConnectionHandler):
    def __init__(self, log_ctl):
        super(MessageDispatcher, self).__init__()
        self._log_ctl = log_ctl
        self._machines = dict()

    def add_agent(self, machine, connection):
        self._machines[machine] = machine
        self.add_connection(machine, connection)

    def send_message(self, machine, data):
        soc = self.get_connection(machine)
        data = remote_device_to_deviceref(data)

        if send_data(soc, data) == False:
            msg = "Connection error from agent %s" % machine.get_id()
            raise ConnectionError(msg)

        result = None
        while True:
            connected_agents = list(self._connection_mapping.keys())

            messages = self.check_connections()
            for msg in messages:
                if msg[1]["type"] == "result" and msg[0] == machine:
                    if result is not None:
                        msg = ("Multiple result messages from the same agent "
                               "'{}'".format(machine.get_id()))
                        raise ConnectionError(msg)
                    result = msg[1]
                else:
                    self._process_message(msg)

            remaining_agents = list(self._connection_mapping.keys())
            if connected_agents != remaining_agents:
                self._handle_disconnects(set(connected_agents)-
                                         set(remaining_agents))

            if result is not None:
                netns = data.get("netns", None)
                return deviceref_to_remote_device(machine, result["result"], netns)

    def wait_for_condition(self, condition_check, timeout=0):
        res = True
        prev_handler = signal.signal(signal.SIGALRM, _timeout_handler)

        def condition_wrapper():
            res = condition_check()
            if res:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, prev_handler)
                logging.debug("Condition passed, disabling timeout alarm")
            return res

        try:
            signal.alarm(timeout)

            wait = True
            while wait:
                connected_agents = list(self._connection_mapping.keys())
                messages = self.check_connections(timeout=1)
                for msg in messages:
                    try:
                        self._process_message(msg)
                        wait = wait and not condition_wrapper()
                    except WaitTimeoutError as exc:
                        logging.error("Waiting for condition timed out!")
                        res = False
                        wait = False

                wait = wait and not condition_wrapper()

                remaining_agents = list(self._connection_mapping.keys())
                if connected_agents != remaining_agents:
                    self._handle_disconnects(set(connected_agents)-
                                             set(remaining_agents))
        except WaitTimeoutError as exc:
            logging.error("Waiting for condition timed out!")
            res = False
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)

        return res

    def handle_messages(self):
        connected_agents = list(self._connection_mapping.keys())

        messages = self.check_connections()

        for msg in messages:
            self._process_message(msg)

        remaining_agents = list(self._connection_mapping.keys())
        if connected_agents != remaining_agents:
            self._handle_disconnects(set(connected_agents)-
                                     set(remaining_agents))
        return True

    def _process_message(self, message):
        if message[1]["type"] == "log":
            record = message[1]["record"]
            self._log_ctl.add_client_log(message[0].get_id(), record)
        elif message[1]["type"] == "result":
            msg = "Received result message from different agent %s" % message[0].get_id()
            logging.debug(msg)
        elif message[1]["type"] == "dev_created":
            machine = self._machines[message[0]]
            try:
                netns = message[1]["netns"]
            except KeyError:
                netns = None
            machine.device_created(message[1]["dev_data"], netns)
        elif message[1]["type"] == "dev_deleted":
            machine = self._machines[message[0]]
            try:
                netns = message[1]["netns"]
            except KeyError:
                netns = None
            machine.device_delete(message[1], netns)
        elif message[1]["type"] == "dev_netns_changed":
            machine = self._machines[message[0]]
            try:
                netns = message[1]["netns"]
            except KeyError:
                netns = None
            machine.device_netns_change(message[1], netns)
        elif message[1]["type"] == "exception":
            raise message[1]["Exception"]
        elif message[1]["type"] == "job_finished":
            machine = self._machines[message[0]]
            machine.job_finished(message[1])
        else:
            msg = "Unknown message type: %s" % message[1]["type"]
            raise ConnectionError(msg)

    def _handle_disconnects(self, disconnected_agents):
        disconnected_agents = set(disconnected_agents)
        for agent in list(disconnected_agents):
            if not agent.get_mapped():
                logging.warn("Agent {} soft-disconnected from the "
                             "controller.".format(agent.get_id()))
                disconnected_agents.remove(agent)

        if len(disconnected_agents) > 0:
            disconnected_names = [x.get_id()
                                  for x in disconnected_agents]
            msg = "Agents " + str(list(disconnected_names)) + \
                  " hard-disconnected from the controller."
            raise ConnectionError(msg)

    def disconnect_agent(self, machine):
        soc = self.get_connection(machine)
        self.remove_connection(soc)
        del self._machines[machine]
