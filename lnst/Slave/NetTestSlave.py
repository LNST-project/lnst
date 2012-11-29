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

import signal
import select, logging
import os
from xmlrpclib import Binary
from tempfile import NamedTemporaryFile
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from lnst.Common.Logs import Logs, log_exc_traceback
from lnst.Common.PacketCapture import PacketCapture
from lnst.Common.XmlRpc import Server
from lnst.Common.Utils import die_when_parent_die
from lnst.Common.NetUtils import scan_netdevs, test_tcp_connection
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.ResourceCache import ResourceCache
from lnst.Common.NetTestCommand import NetTestCommandContext
from lnst.Common.NetTestCommand import CommandException, NetTestCommand
from lnst.Slave.NetConfig import NetConfig
from lnst.Slave.NetConfigDevice import NetConfigDeviceAllCleanup
from lnst.Common.Utils import check_process_running

DefaultRPCPort = 9999

class NetTestSlaveXMLRPC:
    '''
    Exported xmlrpc methods
    '''
    def __init__(self, command_context, config):
        self._netconfig = None
        self._packet_captures = {}
        self._netconfig = NetConfig()
        self._command_context = command_context

        self._copy_targets = {}
        self._copy_sources = {}

        self._cache = ResourceCache(config.get_option("cache", "dir"),
                        config.get_option("cache", "expiration_period"))

        self._resource_table = {}

    def hello(self):
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()

        if check_process_running("NetworkManager"):
            logging.error("=============================================")
            logging.error("NetworkManager is running on a slave machine!")
            logging.error("This might effect test results!")
            logging.error("=============================================")
        return "hello"

    def bye(self):
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()
        self._remove_capture_files()
        return "bye"

    def get_new_logs(self):
        buffer  = Logs.get_buffer()
        logs = buffer.flush()
        return logs

    def get_devices_by_hwaddr(self, hwaddr):
        name_scan = scan_netdevs()
        netdevs = []

        for entry in name_scan:
            if entry["hwaddr"] == hwaddr:
                netdevs.append(entry)

        return netdevs

    def set_device_down(self, hwaddr):
        devs = self.get_devices_by_hwaddr(hwaddr)

        for dev in devs:
            exec_cmd("ip link set %s down" % dev["name"])

        return True

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
        netconfig = self._netconfig.dump_config()

        files = {}
        for dev_id, dev_spec in netconfig.iteritems():
            df_handle = NamedTemporaryFile(delete=False)
            dump_file = df_handle.name
            df_handle.close()

            files[dev_id] = dump_file

            pcap = PacketCapture()
            pcap.set_interface(dev_spec["name"])
            pcap.set_output_file(dump_file)
            pcap.set_filter(filt)
            pcap.start()

            self._packet_captures[dev_id] = pcap

        self._capture_files = files
        return files

    def stop_packet_capture(self):
        netconfig = self._netconfig.dump_config()
        for dev_id in netconfig.keys():
            pcap = self._packet_captures[dev_id]
            pcap.stop()

        return True

    def _remove_capture_files(self):
        for name in self._capture_files.itervalues():
            logging.debug("Removing temporary packet capture file %s", name)
            os.unlink(name)

    def run_command(self, command):
        try:
            cmd_cls = NetTestCommand(self._command_context, command,
                                        self._resource_table)
            return cmd_cls.run()
        except:
            log_exc_traceback()
            cmd_type = command["type"]
            m_id = command["machine_id"]
            msg = "Execution of %s command on machine %s failed" \
                                    % (cmd_type, m_id)
            raise CommandException(msg)

    def machine_cleanup(self):
        NetConfigDeviceAllCleanup()
        self._netconfig.cleanup()
        self._command_context.cleanup()
        self._cache.del_old_entries()
        return True

    def clear_resource_table(self):
        self._resource_table = {}
        return True

    def has_resource(self, res_hash):
        if self._cache.query(res_hash):
            return True

        return False

    def map_resource(self, res_hash, res_type, res_name):
        resource_location = self._cache.get_path(res_hash)

        if not res_type in self._resource_table:
            self._resource_table[res_type] = {}

        self._resource_table[res_type][res_name] = resource_location
        self._cache.renew_entry(res_hash)

        return True

    def add_resource_to_cache(self, file_hash, local_path, name,
                                res_hash, res_type):
        self._cache.add_cache_entry(file_hash, local_path, name, res_type)
        return True

    def start_copy_to(self, filepath=None):
        if filepath in self._copy_targets:
            return ""

        if filepath:
            self._copy_targets[filepath] = open(filepath, "w+b")
        else:
            tmpfile = NamedTemporaryFile("w+b", delete=False)
            filepath = tmpfile.name
            self._copy_targets[filepath] = tmpfile

        return filepath

    def copy_part_to(self, filepath, binary_data):
        if self._copy_targets[filepath]:
            self._copy_targets[filepath].write(binary_data.data)
            return True

        return False

    def finish_copy_to(self, filepath):
        if self._copy_targets[filepath]:
            self._copy_targets[filepath].close()

            del self._copy_targets[filepath]
            return True

        return False

    def start_copy_from(self, filepath):
        if filepath in self._copy_sources or not os.path.exists(filepath):
            return False

        self._copy_sources[filepath] = open(filepath, "rb")
        return True

    def copy_part_from(self, filepath, buffsize):
        data = Binary(self._copy_sources[filepath].read(buffsize))
        return data

    def finish_copy_from(self, filepath):
        if filepath in self._copy_sources:
            self._copy_sources[filepath].close()
            del self._copy_sources[filepath]
            return True

        return False

    def reset_file_transfers(self):
        for file_handle in self._copy_targets.itervalues():
            file_handle.close()
        self._copy_targets = {}

        for file_handle in self._copy_sources.itervalues():
            file_handle.close()
        self._copy_sources = {}

class MySimpleXMLRPCServer(Server):
    def __init__(self, command_context, *args, **kwargs):
        self._finished = False
        self._command_context = command_context
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
                    self._command_context.cleanup()
                    import sys
                    sys.exit()
                    return
                self.handle_request()
            except select.error:
                pass

class NetTestSlave:
    def __init__(self, config, port = DefaultRPCPort):
        die_when_parent_die()

        command_context = NetTestCommandContext()
        server = MySimpleXMLRPCServer(command_context,
                                      ("", port), SimpleXMLRPCRequestHandler,
                                      logRequests = False)
        server.register_die_signal(signal.SIGHUP)
        server.register_die_signal(signal.SIGINT)
        server.register_die_signal(signal.SIGTERM)
        server.register_instance(NetTestSlaveXMLRPC(command_context, config))
        self._server = server

    def run(self):
        self._server.serve_forever_with_signal_check()
