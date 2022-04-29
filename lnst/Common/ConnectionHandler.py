"""
This module defines the base class for connection handling, and helper
functions used in our communication protocol.

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import select
import socket
import logging
import traceback
from multiprocessing.connection import Connection
from lnst.Common.SecureSocket import SecureSocket, SecSocketException

def send_data(s, data):
    try:
        if isinstance(s, SecureSocket):
            s.send_msg(data)
        elif isinstance(s, Connection):
            s.send(data)
        else:
            return False
    except socket.error:
        return False
    return True

def recv_data(s):
    if isinstance(s, SecureSocket):
        try:
            data = s.recv_msg()
        except SecSocketException:
            return ""
    elif isinstance(s, Connection):
        data = s.recv()
    else:
        return None
    return data


class ConnectionHandler(object):
    def __init__(self):
        self._connections = []
        self._connection_mapping = {}

    def check_connections(self, timeout=None):
        return self._check_connections(list(self._connections), timeout)

    def check_connections_by_id(self, connection_ids, timeout=None):
        connections = []
        for con_id in connection_ids:
            connections.append(self._connection_mapping[con_id])
        return self._check_connections(connections, timeout)

    def _check_connections(self, connections, timeout):
        for c in list(connections):
            if c.closed:
                self.remove_connection(c)
                connections.remove(c)

        requests = []
        try:
            rl, wl, xl = select.select(connections, [], [], timeout)
        except select.error:
            logging.debug(traceback.format_exc())
            return []
        for f in rl:
            f_ready = True
            while f_ready:
                try:
                    data = recv_data(f)

                    if data == "":
                        f.close()
                        self.remove_connection(f)
                        f_ready = False
                    elif data is not None:
                        id = self.get_connection_id(f)
                        requests.append((id, data))

                    if f_ready:
                        #poll the file descriptor if there is another message
                        rll, _, _ = select.select([f], [], [], 0)
                        if rll == []:
                            f_ready = False

                except socket.error:
                    f_ready = False
                    f.close()
                    self.remove_connection(f)
                except EOFError:
                    f_ready = False
                    f.close()
                    self.remove_connection(f)

        return requests

    def get_connection(self, id):
        if id in self._connection_mapping:
            return self._connection_mapping[id]
        else:
            return None

    def get_connection_id(self, connection):
        for id in self._connection_mapping:
            if self._connection_mapping[id] == connection:
                return id
        return None

    def add_connection(self, id, connection):
        if id not in self._connection_mapping:
            self._connections.append(connection)
            self._connection_mapping[id] = connection

    def remove_connection(self, connection):
        if connection in self._connections:
            id = self.get_connection_id(connection)
            self._connections.remove(connection)
            del self._connection_mapping[id]

    def remove_connection_by_id(self, id):
        if id in self._connection_mapping:
            connection = self._connection_mapping[id]
            self._connections.remove(connection)
            del self._connection_mapping[id]

    def clear_connections(self):
        self._connections = []
        self._connection_mapping = {}

    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove things that can't be pickled
        state['_connections'] = []
        state['_connection_mapping'] = {}
        return state