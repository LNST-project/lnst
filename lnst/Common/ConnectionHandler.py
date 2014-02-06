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
import cPickle
import socket
from _multiprocessing import Connection
from pyroute2 import IPRSocket

def send_data(s, data):
    try:
        if isinstance(s, socket.SocketType):
            pickled_data = cPickle.dumps(data)
            length = len(pickled_data)

            data_to_send = str(length) + " " + pickled_data
            s.sendall(data_to_send)
        elif isinstance(s, Connection):
            s.send(data)
        else:
            return False
    except socket.error:
        return False
    return True

def recv_data(s):
    if isinstance(s, IPRSocket):
        msg = s.get()
        data = {"type": "netlink", "data": msg}
    elif isinstance(s, socket.SocketType):
        length = ""
        while True:
            c = s.recv(1)
            if c == ' ':
                length = int(length)
                break
            elif c == "":
                return ""
            else:
                length += c
        data = ""

        while len(data)<length:
            c = s.recv(length - len(data))
            if c == "":
                return ""
            else:
                data += c

        data = cPickle.loads(data)
    elif isinstance(s, Connection):
        data = s.recv()
    else:
        return None
    return data


class ConnectionHandler(object):
    def __init__(self):
        self._connections = {}

    def check_connections(self):
        requests = []
        try:
            rl, wl, xl = select.select(self._connections.values(), [], [])
        except select.error:
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
                    else:
                        id = self.get_connection_id(f)
                        requests.append((id, data))

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
        if id in self._connections:
            return self._connections[id]
        else:
            return None

    def get_connection_id(self, connection):
        for id in self._connections:
            if self._connections[id] == connection:
                return id
        return None

    def add_connection(self, id, connection):
        if id not in self._connections:
            self._connections[id] = connection

    def remove_connection(self, connection):
        d = {}
        for key, value in self._connections.iteritems():
            if value != connection:
                d[key] = value
        self._connections = d

    def clear_connections(self):
        self._connections = {}
