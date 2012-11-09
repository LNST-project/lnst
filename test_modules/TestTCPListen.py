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
from multiprocessing import Process, Value
from signal import signal, SIGINT
import ctypes
from lnst.Common.TestsCommon import TestGeneric

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
        self._closecon = Value(ctypes.c_bool, False, lock=True)

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

    def _worker(self, host, port, connections, closecon):
        logging.debug("Starting listener (%s) on port %s " % (host, port))

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
        except socket.error as msg:
            logging.debug(msg)
            return

        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen(1)
        except socket.error as msg:
            logging.debug(msg)
            s.close()
            return

        loop = 1

        while (loop or self._cont) and not closecon.value:
            conn = None
            while conn == None and not closecon.value:
                try:
                    conn, addr = s.accept()
                except socket.timeout as e:
                    continue
                except socket.error as e:
                    logging.debug(e)
                    s.close()
                    return
                except:
                    logging.warning("Unknown exception.")
                    s.close()
                    return

            if conn:
                connections.value += 1
                conn.settimeout(1)
            else:
                continue

            logging.debug('Connected from ' + addr[0] + ' port:' +
                          str(addr[1]))

            while not closecon.value:
                try:
                    data = conn.recv(1024)
                except socket.timeout as e:
                    continue
                except socket.error as e:
                    logging.debug(e)
                    if conn:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()
                    s.close()
                    return

                if not data:
                    logging.debug('Client disconnected: ' + addr[0] +
                                  ' port:' + str(addr[1]))
                    break

            if conn:
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                    conn.close()
                except socket.error as msg:
                    logging.debug(msg)
                    s.close()
                    return

            loop = 0

        s.close()

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

    def _terminate(self, signum, frame):
        self._closecon.value = True
        logging.debug("Listen: terminate called")

    def _set_interrupt_handler(self):
        signal(SIGINT, self._terminate)

    def run(self):
        self._set_interrupt_handler()

        self._parse_options()

        ports = []
        if self._port:
            ports.extend(self._port)
        else:
            r = self._parse_port_range()
            ports.extend(r)

        self.workers = []

        connections = Value('L', 0, lock=True)

        for p in ports:
            w = Process(target=self._worker, args=(self._addr, p, connections, self._closecon))
            w.start()
            self.workers.append(w)


        logging.debug("Waiting for workers ...")
        while len(self.workers) > 0:
            for w in self.workers:
                try:
                    w.join()
                except:
                    continue
                self.workers.remove(w)

        logging.info("Handled %s TCP connections." % connections.value)

        return self.set_pass("Handled %s TCP connections." % connections.value)
