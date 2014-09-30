"""
This module defines MessageDispatcherLite class which is derived from
lnst.NetTestController.MessageDispatcher.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

from lnst.Common.ConnectionHandler import send_data, recv_data
from lnst.Common.ConnectionHandler import ConnectionHandler

class MessageDispatcherLite(ConnectionHandler):
    def __init__(self):
        super(MessageDispatcherLite, self).__init__()

    def add_slave(self, machine, connection):
        self.add_connection(1, connection)

    def send_message(self, machine_id, data):
        soc = self.get_connection(1)

        if send_data(soc, data) == False:
            msg = "Connection error from slave %s" % str(1)
            raise NetTestError(msg)

    def wait_for_result(self, machine_id):
        wait = True
        while wait:
            connected_slaves = self._connection_mapping.keys()

            messages = self.check_connections()

            remaining_slaves = self._connection_mapping.keys()

            for msg in messages:
                if msg[1]["type"] == "result" and msg[0] == 1:
                    wait = False
                    result = msg[1]["result"]
                else:
                    self._process_message(msg)

            if connected_slaves != remaining_slaves:
                disconnected_slaves = set(connected_slaves) -\
                                      set(remaining_slaves)
                msg = "Slaves " + str(list(disconnected_slaves)) + \
                      " disconnected from the controller."
                raise NetTestError(msg)

        return result

    def _process_message(self, message):
        if message[1]["type"] == "log":
            pass
        else:
            msg = "Unknown message type: %s" % message[1]["type"]
            raise NetTestError(msg)

    def disconnect_slave(self, machine_id):
        soc = self.get_connection(machine_id)
        self.remove_connection(soc)
