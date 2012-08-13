"""
This module defines TCPConnect module
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import sys
import socket
import errno
from multiprocessing import Process, Lock
from signal import signal, SIGINT
from time import sleep
from random import randrange, sample
import logging
import re
from Common.TestsCommon import TestGeneric

"""
Test description:
    Test spawns client(s) connecting to TCP port(s) defined by port or
    port_range option. When connected, the client sends random bursts of
    random data to server. If cont option is set the connections are initiated
    again and data is sent to server until interrupted by the controller.

Parameters:
    addr ... mandatory, address to connect to
    port ... mandatory, port to send data
    sleep ... optional, sleep time between bursts, if undefined, the bursts
              are immediate
    cont ... optional, sets continuous mode of connecting, if set connections
             are infinitely re-spawned when closed
"""

class ConnectionWorker():
    def __init__(self, host, port, sleep_time = None, continuous = None):
        self._tlock = Lock()
        self._terminate = 0
        self._host = host
        self._port = port
        self._sleep_time = sleep_time
        self._cont = continuous
        self._ascii = [chr(i) for i in range(0,255)]

    def terminate(self):
        self._tlock.acquire()
        self._terminate=1
        self._tlock.release()

    def run(self):
        loop = True

        while loop:
            loop = (self._cont is not None)
            logging.debug("Starting connection to (%s) port %s " % (self._host,
                          self._port))

            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self._host, self._port))
            except socket.error, msg:
                s.close()
                s = None
                logging.error(msg)
                return

            for txs in range(10, randrange(20,100)):
                self._tlock.acquire()
                if self._terminate:
                    self._tlock.release()
                    logging.debug("Terminating connection on port %s" %
                                  self._port)
                    loop = False
                    break
                else:
                    self._tlock.release()

                rnd_str = "".join(sample(self._ascii, len(self._ascii)))
                data = s.sendall(rnd_str)
                if (self._sleep_time):
                    sleep(self._sleep_time)

            s.close()


class TestTCPConnect(TestGeneric):
    def _parse_options(self):
        addr = self.get_mopt("addr")
        if addr:
            self._host = addr

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

        sleep_time = float(self.get_opt("sleep"))
        if sleep_time:
            self._sleep_time = sleep_time

        cont = self.get_opt("cont")
        if cont:
            self._cont = cont

    def parse_port_range(self):
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

    def _close_connections(self, signum, frame):
        logging.debug("Termination signal delivered ...")
        for cw in self._cw_instances:
            cw.terminate()

    def _set_interrupt_handler(self):
        signal(SIGINT, self._close_connections)

    def run(self):
        self._terminate = 0
        self._host = None
        self._port = None
        self._cont = None
        self._cw_instances = []

        self._set_interrupt_handler()

        self._parse_options()

        ports = []
        if self._port:
            ports.extend(self._port)
        else:
            r = self.parse_port_range()
            ports.extend(r)

        workers = []
        for p in ports:
            cw = ConnectionWorker(self._host, p, self._sleep_time, self._cont)
            self._cw_instances.append(cw)

            w = Process(target=cw.run)
            w.start()
            workers.append(w)

        logging.debug("Waiting for workers ...")
        for w in workers:
            w.join()
