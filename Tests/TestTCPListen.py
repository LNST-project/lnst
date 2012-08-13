"""
This module defines TCPListen module
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import sys
import socket
import errno
import logging
import re
from multiprocessing import Process
from Common.TestsCommon import TestGeneric

"""
Test description:
    Test spawns server(s) listening for TCP connection(s) on port(s) defined by
    port or port_range options. When client connects to the port, server reads
    the data sent and close the connection when no more data is available.
    If cont option is set the connection is reopened and server reads data
    again.

Parameters:
    addr ... optional, address to bind to, if undefined listen on all ifaces
    port ... mandatory, port to listen on
    cont ... optional, if set the listening port is reopened when the
             connection is closed
"""

class TestTCPListen(TestGeneric):
    def __init__(self, command):
        self._addr = None
        self._port = None
        self._cont = None
        TestGeneric.__init__(self, command)

    def _parse_options(self):
        addr = self.get_opt("addr")
        if addr:
            self._addr = addr

        # either port or port_range should be set
        port = self.get_opt("port")
        if port:
            self._port = port
        else:
            port_range = self.get_opt("port_range")
            if port_range:
                self._port_range = port_range
            else:
                e = TestOptionMissing()
                raise e

        cont = self.get_opt("cont")
        if cont:
            self._cont = cont

    def _worker(self, host, port):
        logging.debug("Starting listener (%s) on port %s " % (host, port))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.bind((host, port))
            s.listen(1)
        except socket.error, msg:
            s.close()
            s = None
            logging.error(msg)
            return

        loop = 1

        while loop or self._cont:
            conn, addr = s.accept()
            logging.debug('Connected from ' + addr[0] + ' port:' +
                          str(addr[1]))

            while 1:
                data = conn.recv(1024)
                if not data:
                    logging.debug('Client disconnected: ' + addr[0] +
                                  ' port:' + str(addr[1]))
                    break

            conn.close()
            loop = 0

    def _parse_port_range(self):
        if self._port_range == None:
            return []

        for c in [',','-']:
            s = self._port_range.split(c)
            if len(s) == 2:
                break

        if len(s) != 2:
            logging.error("Port range malformed! ", self._port_range)

        low = int(s[0])
        high = int(s[1]) + 1

        return range(low, high)

    def run(self):
        self._parse_options()

        ports = []
        if self._port:
            ports.extend(self._port)
        else:
            r = self._parse_port_range()
            ports.extend(r)

        workers = []

        for p in ports:
            w = Process(target=self._worker, args=(self._addr, p))
            w.start()
            workers.append(w)


        logging.debug("Waiting for workers ...")
        for w in workers:
            w.join()
