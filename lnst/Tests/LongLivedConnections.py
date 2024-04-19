import time
import select
import socket
import logging
import resource
import threading

from .BaseTestModule import BaseTestModule
from lnst.Common.Parameters import IntParam, IpParam


class BaseLongLivedTestModule(BaseTestModule):
    server_ip = IpParam(mandatory=True)
    server_port = IntParam(mandatory=True)
    duration = IntParam(default=0)  # 0 means run indefinitely, until SIGINT is received
    connections_count = IntParam(default=1)

    def run(self):
        self._running = True
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)

        self._set_rlimit(hard, hard)
        self._start()
        if self.params.duration:
            time.sleep(self.params.duration)
        else:
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logging.info("Interrupted, dying...")

        self._stop()
        self._set_rlimit(soft, hard)

        return (
            self._result
        )  # is set as part of _stop (if # of conns matches expected # of conns)

    def _set_rlimit(self, soft: int, hard: int):
        logging.info(f"Setting RLIMIT_NOFILE to {(soft, hard)}")
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))

    def runtime_estimate(self):
        if not self.params.duration:
            return 0

        return self.params.duration + 5


class LongLivedServer(BaseLongLivedTestModule):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._running = False
        self._connections = []

        self._polling_thread = None
        self._listening_thread = None

    def _start(self):
        self._running = True
        self._listening_thread = threading.Thread(target=self._listen)
        self._listening_thread.start()

        self._polling_thread = threading.Thread(target=self._poll_connections)
        self._polling_thread.start()

    def _stop(self):
        logging.info("Stopping LongLivedServer server")
        self._running = False

        self._listening_thread.join()
        self._polling_thread.join()
        
        self._result = (
            True if len(self._connections) == self.params.connections_count else False
        )

        for conn in self._connections:
            conn.close()

    def _listen(self):
        with socket.socket(
            self.params.server_ip.family, socket.SOCK_STREAM
        ) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((str(self.params.server_ip), self.params.server_port))
            server_socket.listen(65536)

            logging.info(
                f"TCP server started on {self.params.server_ip}:{self.params.server_port}"
            )
            while self._running:
                try:
                    ready, _, _ = select.select([server_socket], [], [], 1)
                except ValueError:
                    continue

                if not ready:
                    time.sleep(1)  # prevent active polling
                    continue

                for conn in ready:
                    client_socket, client_address = server_socket.accept()
                    client_socket.setblocking(False)

                    self._connections.append(client_socket)

    def _poll_connections(self):
        while self._running:  # no need to lock due to GIL
            if not self._connections:
                time.sleep(1)
                continue

            try:
                ready, _, _ = select.select(self._connections, [], [], 1)
            except ValueError:
                continue


class LongLivedClient(BaseLongLivedTestModule):
    client_ip = IpParam(mandatory=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._connections = []

    def _start(self):
        for _ in range(self.params.connections_count):
            conn = self._start_connection()
            self._connections.append(conn)

        logging.info(f"All connections established by {self}")

    def _stop(self):
        self._result = (
            True if len(self._connections) == self.params.connections_count else False
        )

        for conn in self._connections:
            conn.close()

        self._connections = []

    def _start_connection(self):
        sck = socket.socket(self.params.server_ip.family, socket.SOCK_STREAM)
        sck.bind(
            (str(self.params.client_ip), 0)
        )  # needs to be binded to specific IP to respect flow IPs
        sck.connect((str(self.params.server_ip), self.params.server_port))

        return sck
