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

from Common.Logs import Logs
import signal
import select, logging
from Common.XmlRpc import Server
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from NetConfig.NetConfig import NetConfig
from NetConfig.NetConfigDevice import NetConfigDeviceAllCleanup
from NetTestCommand import NetTestCommand, CommandException
from Common.Utils import die_when_parent_die

DefaultRPCPort = 9999

class NetTestSlaveXMLRPC:
    '''
    Exported xmlrpc methods
    '''
    def __init__(self):
        self._netconfig = None

    def hello(self):
        return "hello"

    def set_logging(self, logger_address, port):
        """
        Server side setup logging to server side.

        @param logger_address: Address of running logger.
        """
        Logs.append_network_hadler(logger_address, port)
        return True

    def netconfig_set(self, machine_xml_string, config_xml_string):
        self._netconfig = NetConfig(machine_xml_string, config_xml_string)
        self._netconfig.configure_all()
        return True

    def netconfig_dump(self):
        return self._netconfig.dump_config().items()

    def netconfig_clear(self):
        self._netconfig.deconfigure_all()
        self.__init__()
        return True

    def run_command(self, command):
        try:
            return NetTestCommand(command).run()
        except:
            import sys, traceback
            type, value, tb = sys.exc_info()
            logging.error(''.join(traceback.format_exception(type, value, tb)))
            raise CommandException(command)

    def machine_cleanup(self):
        NetConfigDeviceAllCleanup()
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
