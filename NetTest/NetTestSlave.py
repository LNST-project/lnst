"""
This module defines NetConfigSlave class which does spawns xmlrpc server and
runs controller's commands

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

from Common.Logs import Logs, log_exc_traceback
import signal
import select, logging
import os
from Common.PacketCapture import PacketCapture
from Common.XmlRpc import Server
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from NetConfig.NetConfig import NetConfig
from NetConfig.NetConfigDevice import NetConfigDeviceAllCleanup
from NetTest.NetTestCommand import NetTestCommand, CommandException
from Common.Utils import die_when_parent_die
from Common.NetUtils import scan_netdevs

DefaultRPCPort = 9999

class NetTestSlaveXMLRPC:
    '''
    Exported xmlrpc methods
    '''
    def __init__(self):
        self._netconfig = None
        self._packet_captures = {}
        self._netconfig = NetConfig()

    def hello(self):
        return "hello"

    def set_logging(self, logger_address, port):
        """
        Server side setup logging to server side.

        @param logger_address: Address of running logger.
        """
        Logs.append_network_hadler(logger_address, port)
        return True

    def get_devices_by_hwaddr(self, hwaddr):
        name_scan = scan_netdevs()
        netdevs = []

        for entry in name_scan:
            if entry["hwaddr"] == hwaddr:
                netdevs.append(entry)

        return netdevs

    def get_interface_info(self, if_id):
        if_config = self._netconfig.get_interface_config(if_id)
        info = {}

        if "name" in if_config:
            info["name"] = if_config["name"]

        if "hwaddr" in if_config:
            info["hwaddr"] = if_config["hwaddr"]

        return info

    def configure_interface(self, if_id, config):
        self._netconfig.add_interface_config(if_id, config)
        self._netconfig.configure(if_id)
        return True

    def deconfigure_interface(self, if_id):
        self._netconfig.deconfigure(if_id)
        self._netconfig.remove_interface_config(if_id)
        return True

    def netconfig_dump(self):
        return self._netconfig.dump_config().items()

    def start_packet_capture(self, filt):
        logging_dir = Logs.get_logging_root_path()
        logging_dir = os.path.abspath(logging_dir)
        netconfig = self._netconfig.dump_config()

        files = []
        for dev_id, dev_spec in netconfig.iteritems():
            dump_file = os.path.join(logging_dir, "%s.pcap" % dev_id)
            files.append(dump_file)

            pcap = PacketCapture()
            pcap.set_interface(dev_spec["name"])
            pcap.set_output_file(dump_file)
            pcap.set_filter(filt)
            pcap.start()

            self._packet_captures[dev_id] = pcap

        return files

    def stop_packet_capture(self):
        netconfig = self._netconfig.dump_config()
        for dev_id in netconfig.keys():
            pcap = self._packet_captures[dev_id]
            pcap.stop()

        return True

    def run_command(self, command):
        try:
            return NetTestCommand(command).run()
        except:
            log_exc_traceback()
            raise CommandException(command)

    def machine_cleanup(self):
        NetConfigDeviceAllCleanup()
        self._netconfig.cleanup()
        return True

class MySimpleXMLRPCServer(Server):
    def __init__(self, *args, **kwargs):
        self._finished = False
        Server.__init__(self, *args, **kwargs)

    def register_die_signal(self, signum):
        signal.signal(signum, self._signal_die_handler)

    def _signal_die_handler(self, signum, frame):
        logging.info("Caught signal %d -> dying" % signum)
        self._finished = True

    def serve_forever_with_signal_check(self):
        while True:
            try:
                if self._finished:
                    import sys
                    sys.exit()
                    return
                self.handle_request()
            except select.error:
                pass

class NetTestSlave:
    def __init__(self, port = DefaultRPCPort):
        die_when_parent_die()

        server = MySimpleXMLRPCServer(("", port), SimpleXMLRPCRequestHandler,
                                      logRequests = False)
        server.register_die_signal(signal.SIGHUP)
        server.register_die_signal(signal.SIGINT)
        server.register_die_signal(signal.SIGTERM)
        server.register_instance(NetTestSlaveXMLRPC())
        self._server = server

    def run(self):
        self._server.serve_forever_with_signal_check()
