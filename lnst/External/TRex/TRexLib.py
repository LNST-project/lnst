import os
import sys
import time
import logging
import subprocess
import tempfile
import signal
import yaml

TREX_CLI_DEFAULT_PARAMS = {
        "warmup_time": 5,
        "server_hostname": "localhost",
        "trex_stl_path": 'trex_client/interactive',
        "msg_size": 64
        }

class TRexCli:
    """
    TRex client.
    In its constructor, it accepts any object with the following attributes
        - trex_dir (str): Path to the trex directory
        - ports (list): List of integer values ranging 0 to len(flows)
        - flows (list): A list of tuples of dictionaries each containing the following keys:
            mac_addr: Source MAC address of the flow
            pci_addr: PCI address of the interface to use
            ip_addr: Source IP address of the flow
        - duration (int): Integer value of the duration of the test
        - warmup_time (int): Time to wait before starting to take measurements. Default: 5
        - server_hostname (str): Host where the server is running.
        - msg_size (int): Message size
    """
    trex_stl_path = 'trex_client/interactive'

    def __init__(self, params):
        self.params = params
        self.results = {}
        for key in TREX_CLI_DEFAULT_PARAMS:
            if key not in params.__dict__:
                setattr(self.params, key, TREX_CLI_DEFAULT_PARAMS[key])

    def get_results(self):
        return self.results

    def run(self):
        sys.path.insert(0, os.path.join(self.params.trex_dir,
                                        self.trex_stl_path))

        from trex.stl import api as trex_api

        try:
            return self._run(trex_api)
        except trex_api.TRexError as e:
            raise TRexError(str(e))

    def _run(self, trex_api):
        client = trex_api.STLClient(server=self.params.server_hostname)
        client.connect()

        try:
            client.acquire(ports=self.params.ports, force=True)
        except:
            self.results["msg"] = "Failed to acquire ports"
            return False

        try:
            client.reset(ports=self.params.ports)
        except:
            client.release(ports=self.params.ports)
            self.results["msg"] = "Failed to reset ports"
            return False

        for i, (src, dst) in enumerate(self.params.flows):
            L2 = trex_api.Ether(
                    src=str(src["mac_addr"]),
                    dst=str(dst["mac_addr"]))
            L3 = trex_api.IP(
                    src=str(src["ip_addr"]),
                    dst=str(dst["ip_addr"]))
            L4 = trex_api.UDP()
            base_pkt = L2/L3/L4

            pad = max(0, self.params.msg_size - len(base_pkt)) * 'x'
            packet = base_pkt/pad

            trex_packet = trex_api.STLPktBuilder(pkt=packet)

            trex_stream = trex_api.STLStream(
                    packet=trex_packet,
                    mode=trex_api.STLTXCont(percentage=100))

            port = self.params.ports[i]
            client.add_streams(trex_stream, ports=[port])

        client.set_port_attr(ports=self.params.ports, promiscuous=True)


        measurements = []

        client.start(ports=self.params.ports)

        time.sleep(self.params.warmup_time)

        client.clear_stats(ports=self.params.ports)
        self.results["start_time"] = time.time()

        for i in range(self.params.duration):
            time.sleep(1)
            measurements.append(dict(timestamp=time.time(),
                                     measurement=client.get_stats(
                                         ports=self.params.ports,
                                         sync_now=True)))

        client.stop(ports=self.params.ports)
        client.release(ports=self.params.ports)

        self.results["data"] = measurements
        return True

class TRexSrv:
    """
    TRex server. This class runs TRex in server mode and waits for it to be killed

    In its constructor, it accepts any object with the following attributes
        - trex_dir (str): Path to the trex directory
        - flows (list): A list of tuples of dictionaries each containing the following keys:
            mac_addr: Source MAC address of the flow
            pci_addr: PCI address of the interface to use
            ip_addr: Source IP address of the flow
        - cores (list): List of CPU cores to use
    """
    def __init__(self, params):
        self.params = params

    def get_results(self):
        return None

    def run(self):
        trex_server_conf = [{'port_limit': len(self.params.flows),
                             'version': 2,
                             'interfaces': [],
                             'platform': {
                                 'dual_if': [{
                                     'socket': 0,
                                     'threads': self.params.cores}],
                                 'latency_thread_id': 0,
                                 'master_thread_id': 1},
                             'port_info': []}]

        for src, dst in self.params.flows:
            short_pci_addr = src["pci_addr"].partition(':')[2]
            trex_server_conf[0]['interfaces'].append(short_pci_addr)
            trex_server_conf[0]['port_info'].append(
                    {'src_mac': str(src["mac_addr"]),
                     'dest_mac': str(dst["mac_addr"])})

        with tempfile.NamedTemporaryFile(mode="w+") as cfg_file:
            yaml.dump(trex_server_conf, cfg_file)
            cfg_file.flush()
            os.fsync(cfg_file.file.fileno())

            os.chdir(self.params.trex_dir)
            server = subprocess.Popen(
                    [os.path.join(self.params.trex_dir, "t-rex-64"),
                        "--cfg", cfg_file.name, "-i"],
                    stdin=open('/dev/null'), stdout=open('/dev/null','w'),
                    stderr=subprocess.PIPE, close_fds=True)

            self._wait_for_interrupt()

            server.send_signal(signal.SIGINT)
            out, err = server.communicate()
            if err:
                logging.error(err)
                return False
        return True

    def _wait_for_interrupt(self):
        class InterruptException(Exception):
            pass

        def handler(signum, frame):
            raise InterruptException

        try:
            old_handler = signal.signal(signal.SIGINT, handler)
            signal.pause()
        except InterruptException:
            pass
        finally:
            signal.signal(signal.SIGINT, old_handler)

class TRexError(Exception):
    pass

class TRexParams:
    """
    TRexParams is a simple class that encapsulates a dictionary as attributes
    """
    def __init__(self, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __str__(self):
        string = ""
        for key, val in list(self.__dict__.items()):
            string += "%s: %s\n" % (key, str(val))
        return string

    def __iter__(self):
        for attr, val in list(self.__dict__.items()):
            yield (attr, val)

    def __setitem__(self, name, val):
        setattr(self, name, val)

    def __getitem__(self, name, val):
        getattr(self, name, val)
