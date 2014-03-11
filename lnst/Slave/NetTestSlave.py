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
import sys, traceback
import datetime
import socket
import dbus
from time import sleep
from xmlrpclib import Binary
from tempfile import NamedTemporaryFile
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.PacketCapture import PacketCapture
from lnst.Common.Utils import die_when_parent_die
from lnst.Common.NetUtils import scan_netdevs, test_tcp_connection
from lnst.Common.NetUtils import normalize_hwaddr
from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.ResourceCache import ResourceCache
from lnst.Common.NetTestCommand import NetTestCommandContext
from lnst.Common.NetTestCommand import CommandException, NetTestCommand
from lnst.Slave.NmConfigDevice import is_nm_managed_by_name
from lnst.Common.Utils import check_process_running
from lnst.Common.ConnectionHandler import recv_data, send_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Config import lnst_config
from lnst.Common.NetTestCommand import NetTestCommandConfig
from lnst.Slave.InterfaceManager import InterfaceManager

DefaultRPCPort = 9999

class SlaveMethods:
    '''
    Exported xmlrpc methods
    '''
    def __init__(self, command_context, log_ctl, if_manager):
        self._packet_captures = {}
        self._if_manager = if_manager
        self._command_context = command_context
        self._log_ctl = log_ctl

        self._capture_files = {}
        self._copy_targets = {}
        self._copy_sources = {}
        self._system_config = {}

        self._cache = ResourceCache(lnst_config.get_option("cache", "dir"),
                        lnst_config.get_option("cache", "expiration_period"))

        self._resource_table = {'module': {}, 'tools': {}}

    def hello(self, recipe_path):
        self.machine_cleanup()

        logging.info("Recieved a controller connection.")
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()

        self._if_manager.rescan_devices()

        date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        self._log_ctl.set_recipe(recipe_path, expand=date)
        sleep(1)

        if check_process_running("NetworkManager"):
            logging.warning("=============================================")
            logging.warning("NetworkManager is running on a slave machine!")
            if lnst_config.get_option("environment", "use_nm"):
                logging.warning("Support of NM is still experimental!")
            else:
                logging.warning("Usage of NM is disabled!")
            logging.warning("=============================================")
        return "hello"

    def bye(self):
        self.restore_system_config()
        self.clear_resource_table()
        self._cache.del_old_entries()
        self.reset_file_transfers()
        self._remove_capture_files()
        return "bye"

    def kill_cmds(self):
        logging.info("Killing all forked processes.")
        self._command_context.cleanup()
        return "Commands killed"

    def map_if_by_hwaddr(self, if_id, hwaddr):
        devices = self.get_devices_by_hwaddr(hwaddr)

        if len(devices) == 1:
            dev = self._if_manager.get_device_by_hwaddr(hwaddr)
            self._if_manager.map_if(if_id, dev.get_if_index())

        return devices

    def get_devices_by_devname(self, devname):
        name_scan = self._if_manager.get_devices()
        netdevs = []

        for entry in name_scan:
            if entry["name"] == devname:
                netdevs.append(entry)

        return netdevs

    def get_devices_by_hwaddr(self, hwaddr):
        devices = self._if_manager.get_devices()
        matched = []
        for dev in devices:
            if dev.get_hwaddr() == hwaddr:
                entry = {"name": dev.get_name(),
                         "hwaddr": dev.get_hwaddr()}
                matched.append(entry)

        return matched

    def set_device_up(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        dev.up()
        return True

    def set_device_down(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        dev.down()
        return True

    def set_unmapped_device_down(self, hwaddr):
        dev = self._if_manager.get_device_by_hwaddr(hwaddr)
        dev.down()
        return True

    def configure_interface(self, if_id, config):
        device = self._if_manager.get_mapped_device(if_id)
        device.set_configuration(config)
        device.configure()
        return True

    def create_soft_interface(self, if_id, config):
        return self._if_manager.create_device_from_config(if_id, config)

    def deconfigure_interface(self, if_id):
        device = self._if_manager.get_mapped_device(if_id)
        device.clear_configuration()
        return True

    def start_packet_capture(self, filt):
        files = {}
        for if_id, dev in self._if_manager.get_mapped_devices().iteritems():
            dev_name = dev.get_name()

            df_handle = NamedTemporaryFile(delete=False)
            dump_file = df_handle.name
            df_handle.close()

            files[if_id] = dump_file

            pcap = PacketCapture()
            pcap.set_interface(dev_name)
            pcap.set_output_file(dump_file)
            pcap.set_filter(filt)
            pcap.start()

            self._packet_captures[if_id] = pcap

        self._capture_files = files
        return files

    def stop_packet_capture(self):
        if self._packet_captures == None:
            return True

        for if_index, pcap in self._packet_captures.iteritems():
            pcap.stop()

        self._packet_captures.clear()

        return True

    def _remove_capture_files(self):
        for key, name in self._capture_files.iteritems():
            logging.debug("Removing temporary packet capture file %s", name)
            os.unlink(name)

        self._capture_files.clear()

    def _update_system_config(self, options, persistent):
        system_config = self._system_config
        for opt in options:
            option = opt["name"]
            prev = opt["previous_val"]
            curr = opt["current_val"]

            if persistent:
                if option in system_config:
                    del system_config[option]
            else:
                if not option in system_config:
                    system_config[option] = {"initial_val": prev}
                system_config[option]["current_val"] = curr

    def restore_system_config(self):
        logging.info("Restoring system configuration")
        for option, values in self._system_config.iteritems():
            try:
                cmd_str = "echo \"%s\" >%s" % (values["initial_val"], option)
                (stdout, stderr) = exec_cmd(cmd_str)
            except ExecCmdFail:
                logging.warn("Unable to restore '%s' config option!", option)
                return False

        self._system_config = {}
        return True

    def run_command(self, command):
        cmd = NetTestCommand(self._command_context, command,
                                    self._resource_table, self._log_ctl)
        self._command_context.add_cmd(cmd)

        res = cmd.run()
        if not cmd.forked():
            self._command_context.del_cmd(cmd)

        if command["type"] == "config":
            if res["passed"]:
                self._update_system_config(res["res_data"]["options"],
                                           command["persistent"])
            else:
                err = "Error occured while setting system "\
                      "configuration (%s)" % res["res_data"]["err_msg"]
                logging.error(err)

        return res

    def kill_command(self, id):
        cmd = self._command_context.get_cmd(id)
        cmd.kill(None)
        self._command_context.del_cmd(cmd)
        return cmd.get_result()

    def machine_cleanup(self):
        logging.info("Performing machine cleanup.")
        self._command_context.cleanup()
        self._if_manager.deconfigure_all()
        self._if_manager.clear_if_mapping()
        self._cache.del_old_entries()
        self.restore_system_config()
        self._remove_capture_files()
        return True

    def clear_resource_table(self):
        self._resource_table = {'module': {}, 'tools': {}}
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

class ServerHandler(object):
    def __init__(self, addr):
        self._connection_handler = ConnectionHandler()
        try:
            self._s_socket = socket.socket()
            self._s_socket.bind(addr)
            self._s_socket.listen(1)
        except socket.error as e:
            logging.error(e[1])
            exit(1)

        self._c_socket = None

    def accept_connection(self):
        self._c_socket, addr = self._s_socket.accept()
        self._c_socket = (self._c_socket, addr[0])
        logging.info("Recieved connection from %s" % self._c_socket[1])

        self._connection_handler.add_connection(self._c_socket[1],
                                                self._c_socket[0])
        return self._c_socket

    def get_ctl_sock(self):
        if self._c_socket != None:
            return self._c_socket[0]
        else:
            return None

    def get_messages(self):
        messages = self._connection_handler.check_connections()

        #push ctl messages to the end of message queue, this ensures that
        #update messages are handled first
        ctl_msgs = []
        non_ctl_msgs = []
        for msg in messages:
            if msg[0] == self._c_socket[1]:
                ctl_msgs.append(msg)
            else:
                non_ctl_msgs.append(msg)
        messages = non_ctl_msgs + ctl_msgs

        addr = self._c_socket[1]
        if self._connection_handler.get_connection(addr) == None:
            logging.info("Lost controller connection.")
            self._c_socket = None
        return messages

    def send_data_to_ctl(self, data):
        if self._c_socket != None:
            return send_data(self._c_socket[0], data)
        else:
            return False

    def add_connection(self, id, connection):
        self._connection_handler.add_connection(id, connection)

    def remove_connection(self, key):
        connection = self._connection_handler.get_connection(key)
        self._connection_handler.remove_connection(connection)

    def clear_connections(self):
        self._connection_handler.clear_connections()

    def update_connections(self, connections):
        for key, connection in connections.iteritems():
            self.remove_connection(key)
            self.add_connection(key, connection)

class NetTestSlave:
    def __init__(self, log_ctl, port = DefaultRPCPort):
        die_when_parent_die()

        self._cmd_context = NetTestCommandContext()
        self._if_manager = InterfaceManager()
        self._methods = SlaveMethods(self._cmd_context, log_ctl,
                                     self._if_manager)
        self._server_handler = ServerHandler(("", port))

        self.register_die_signal(signal.SIGHUP)
        self.register_die_signal(signal.SIGINT)
        self.register_die_signal(signal.SIGTERM)

        self._finished = False

        self._log_ctl = log_ctl

        self._server_handler.add_connection('netlink',
                                            self._if_manager.get_nl_socket())

    def run(self):
        while not self._finished:
            if self._server_handler.get_ctl_sock() == None:
                self._log_ctl.cancel_connection()
                try:
                    logging.info("Waiting for connection.")
                    self._server_handler.accept_connection()
                except socket.error:
                    continue
                self._log_ctl.set_connection(
                                            self._server_handler.get_ctl_sock())

            msgs = self._server_handler.get_messages()

            for msg in msgs:
                self._process_msg(msg[1])

        self._methods.machine_cleanup()

    def _process_msg(self, msg):
        if msg["type"] == "command":
            method = getattr(self._methods, msg["method_name"], None)
            if method != None:
                try:
                    result = method(*msg["args"])
                except:
                    log_exc_traceback()
                    type, value, tb = sys.exc_info()
                    exc_trace = ''.join(traceback.format_exception(type,
                                                                   value, tb))
                    response = {"type": "exception", "Exception": value}

                    self._server_handler.send_data_to_ctl(response)
                    return

                if result != None:
                    response = {"type": "result", "result": result}
                    self._server_handler.send_data_to_ctl(response)
            else:
                err = "Method '%s' not supported." % msg["method_name"]
                response = {"type": "error", "err": err}
                self._server_handler.send_data_to_ctl(response)
        elif msg["type"] == "log":
            logger = logging.getLogger()
            record = logging.makeLogRecord(msg["record"])
            logger.handle(record)
        elif msg["type"] == "exception":
            if msg["cmd_id"] != None:
                logging.debug("Recieved an exception from command with id: %s"
                                % msg["cmd_id"])
            else:
                logging.debug("Recieved an exception from foreground command")
            logging.debug(msg["Exception"])
            cmd = self._cmd_context.get_cmd(msg["cmd_id"])
            cmd.join()
            self._cmd_context.del_cmd(cmd)
            self._server_handler.send_data_to_ctl(msg)
        elif msg["type"] == "result":
            if msg["cmd_id"] == None:
                del msg["cmd_id"]
                self._server_handler.send_data_to_ctl(msg)
                cmd = self._cmd_context.get_cmd(None)
                cmd.join()
                self._cmd_context.del_cmd(cmd)
            else:
                cmd = self._cmd_context.get_cmd(msg["cmd_id"])
                cmd.join()
                del msg["cmd_id"]

                cmd.set_result(msg["result"])
                if cmd.finished():
                    msg["result"] = cmd.get_result()
                    self._server_handler.send_data_to_ctl(msg)
                    self._cmd_context.del_cmd(cmd)
        elif msg["type"] == "netlink":
            self._if_manager.handle_netlink_msgs(msg["data"])
        else:
            raise Exception("Recieved unknown command")

        pipes = self._cmd_context.get_read_pipes()
        self._server_handler.update_connections(pipes)

    def register_die_signal(self, signum):
        signal.signal(signum, self._signal_die_handler)

    def _signal_die_handler(self, signum, frame):
        logging.info("Caught signal %d -> dying" % signum)
        self._finished = True
