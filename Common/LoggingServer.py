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
    def __init__(self, root_path, debug):
        self.pid = None
        self.stopped = False
        self.root_path = root_path
        self.debug = debug
        self.childSocket = {}
        self.read_pipe = None
        self.write_pipe = None


    def server_stop_handler(self, sig, frame):
        """
        Call function. Used for signal handle.
        """
        os.close(self.read_pipe)
        if (sig == signal.SIGTERM):
            for sock in self.childSocket.itervalues():
                sock[2].close()
            sys.exit()


    def start(self):
        """
        Start logging server as separate process.

        @param port: Port on which logging server listen.
        @return: Pid of logging process.
        """
        self.read_pipe, self.write_pipe = os.pipe()
        self.pid = os.fork()
        if not self.pid:
            os.close(self.write_pipe)
            die_when_parent_die()
            signal.signal(signal.SIGTERM, self.server_stop_handler)
            self._forked()
        else:
            os.close(self.read_pipe)
            time.sleep(0.5)


    def prepare_logging(self, root_path, sock):
        address = sock.getpeername()[0]
        slave_root_path = os.path.join(root_path, address)
        try:
            os.mkdir(slave_root_path)
        except OSError, e:
            if e.errno != 17:
                raise
        logger = logging.getLogger(address)
        Logs(self.debug, False, logger, log_root=slave_root_path,
                     to_display=False, date="")
        return (logger, address, sock)


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
        wait_socket = [self.read_pipe]
        while True:
            (r,w,e) = select.select(wait_socket, [], [])
            if (self.read_pipe in r):
                slave_ip = os.read(self.read_pipe, 4096)
                host, port = slave_ip.split()

                try:
                    csock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    csock.connect((host, int(port)))
                except socket.error:
                    logging.debug("Failed to connect to slave: "+ slave_ip)
                else:
                    slave = self.prepare_logging(self.root_path, csock)
                    self.childSocket[csock.fileno()] = slave
                    wait_socket.append(slave[2].fileno())
                finally:
                    r.remove(self.read_pipe)

            for so in r:
                if not self.recv_slave_log(*self.childSocket[so]):
                    self.childSocket[so][2].close()
                    del self.childSocket[so]
                    wait_socket.remove(so)


    def addSlave(self, hostname, port):
        os.write(self.write_pipe, hostname+' '+port)


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
    l = LoggingServer()
    l.start()
    raw_input()
    l.stop()
