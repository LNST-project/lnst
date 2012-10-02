"""
Server-like logging handler.
Stores logged messages in a buffer. Every time a new message is emitted it
checks for incoming connections. If a connection is established it flushes the
messages stored in the buffer to the connecting client.

Copyright 2012 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import socket, struct, pickle
import logging

DEFAULT_LOG_PORT = 9998

class ServerHandler(logging.Handler):
    def __init__(self, port=DEFAULT_LOG_PORT):
        logging.Handler.__init__(self)
        self.port = port

        self.sock = None
        self.buf = []

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setblocking(0)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)

    def makePickle(self, record):
        """
        Pickles the record in binary format with a length prefix, and
        returns it ready for transmission across the socket.

        Function taken from class SocketHandler from standard python
        library logging.handlers
        """
        d = dict(record.__dict__)
        d['msg'] = record.getMessage()
        d['args'] = None
        d['exc_info'] = None
        s = pickle.dumps(d, 1)
        slen = struct.pack(">L", len(s))
        return slen + s

    def emit(self, record):
        try:
            s = self.makePickle(record)
            self.buf.append(s)
            self.send_all()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            logging.Handler.handleError(self, record)

    def client_connection(self):
        if self.sock == None:
            try:
                self.sock = self.server_socket.accept()[0]
                return True
            except:
                self.sock = None
                return False
        else:
            return True

    def send_all(self):
        if self.client_connection():
            sent = len(self.buf)
            for record in self.buf:
                if not self.send(record):
                    sent = self.buf.index(record)
                    break

            self.buf = self.buf[sent:]

    def send(self, record):
        try:
            if hasattr(self.sock, "sendall"):
                self.sock.sendall(record)
            else:
                sentsofar = 0
                left = len(record)
                while left > 0:
                    sent = self.sock.send(record[sentsofar:])
                    sentsofar = sentsofar + sent
                    left = left - sent
            return True
        except socket.error:
            self.sock.close()
            self.sock = None
            return False

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

        self.server_socket.close()
        self.server_socket = None

        self.buf = []

        logging.Handler.close(self)
