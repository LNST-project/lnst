"""
Logging server.
Listen connection from logging client.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""

import socket, struct, cPickle, logging
from Common.Logs import Logs
import signal, sys, os, select, time
from Common.Utils import die_when_parent_die


class LoggingServer:
    DEFAULT_PORT = 9998
    def __init__(self, port, root_path, debug):
        self.port = port
        self.pid = None
        self.socket = None
        self.stopped = False
        self.root_path = root_path
        self.debug = debug
        self.childSocket = {}


    def server_stop_handler(self, sig, frame):
        """
        Call function. Used for signal handle.
        """
        if (sig == signal.SIGTERM):
            for sock in self.childSocket.itervalues():
                sock[2].close()
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
            sys.exit()


    def start(self):
        """
        Start logging server as separate process.

        @param port: Port on which logging server listen.
        @return: Pid of logging process.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind(('0.0.0.0',self.port))
        except socket.error, e:
            if (e.errno == 98):
                logging.error("Another Logging server listen"
                              " on port %d" % self.port)
            raise
        self.pid = os.fork()
        if not self.pid:
            die_when_parent_die()
            signal.signal(signal.SIGTERM, self.server_stop_handler)
            self._forked()
        else:
            time.sleep(0.5)


    def prepare_logging(self, root_path, sock):
        address = sock[1][0]
        slave_root_path = os.path.join(root_path, address)
        try:
            os.mkdir(slave_root_path)
        except OSError, e:
            if e.errno != 17:
                raise
        logger = logging.getLogger(address)
        Logs(self.debug, False, logger,
                     log_root=slave_root_path,
                             to_display=False)
        return (logger, address, sock[0])


    def recv_slave_log(self, logger, address, sock):
        try:
            dataLen = sock.recv(4)
            if dataLen == '':
                raise Exception("Client %s close connection."
                                % (address))
            dataLen = struct.unpack('>L',dataLen)[0]
            data = ''
            while (len(data) != dataLen):
                d = sock.recv(dataLen)
                if d == '':
                    print "Client %s close connection."% (address)
                    raise Exception("Client %s close connection."
                                    % (address))
                data += d
            report = cPickle.loads(data)
            record = logging.makeLogRecord(report)
            record.address = "(" + address + ")"
            logger.handle(record)
        except Exception,e:
            logger.debug(e)
            return False
        return True


    def _forked(self):
        """
        Start logging server.

        @param port: Port for listening.
        """
        self.socket.listen(100)
        wait_socket = [self.socket.fileno()]
        while True:
            (r,w,e) = select.select(wait_socket, [], [])
            if (self.socket.fileno() in r):
                csock = self.socket.accept()
                slave = self.prepare_logging(self.root_path, csock)
                self.childSocket[csock[0].fileno()] = slave
                wait_socket.append(slave[2].fileno())
                r.remove(self.socket.fileno())
            for so in r:
                if not self.recv_slave_log(*self.childSocket[so]):
                    self.childSocket[so][2].close()
                    del self.childSocket[so]
                    wait_socket.remove(so)
        self.socket.close()
        sys.exit()


    def stop(self):
        if self.pid and not self.stopped:
            self.stopped = True
            os.kill(self.pid, signal.SIGTERM)
            try:
                os.waitpid(self.pid, 0)
            except OSError, e:
                if e.errno == 10:
                    pass


    def getpid(self):
        return self.pid


if __name__ == '__main__':
    logger = logging.getLogger()
    c = logging.FileHandler("out.txt")
    logger.addHandler(c)
    l = LoggingServer(LoggingServer.DEFAULT_PORT)
    l.start()
    raw_input()
    l.stop()
