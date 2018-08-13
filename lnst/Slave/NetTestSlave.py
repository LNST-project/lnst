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
import logging
import os, stat
import sys, traceback
import datetime
import socket
import ctypes
import multiprocessing
import imp
import types
from time import sleep, time
from inspect import isclass
from tempfile import NamedTemporaryFile
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.PacketCapture import PacketCapture
from lnst.Common.Utils import die_when_parent_die
from lnst.Common.ExecCmd import exec_cmd, ExecCmdFail
from lnst.Common.ResourceCache import ResourceCache
from lnst.Common.NetTestCommand import NetTestCommandContext
from lnst.Common.NetTestCommand import NetTestCommand
from lnst.Common.NetTestCommand import DEFAULT_TIMEOUT
from lnst.Common.Utils import check_process_running
from lnst.Common.Utils import is_installed
from lnst.Common.ConnectionHandler import send_data
from lnst.Common.ConnectionHandler import ConnectionHandler
from lnst.Common.Config import DefaultRPCPort
from lnst.Common.DeviceRef import DeviceRef
from lnst.Common.LnstError import LnstError
from lnst.Common.DeviceError import DeviceDeleted, DeviceDisabled
from lnst.Common.DeviceError import DeviceConfigValueError
from lnst.Common.TestModule import BaseTestModule
from lnst.Common.Parameters import Parameters, DeviceParam
from lnst.Common.IpAddress import ipaddress
from lnst.Common.Version import lnst_version
from lnst.Slave.Job import Job, JobContext
from lnst.Slave.InterfaceManager import InterfaceManager
from lnst.Slave.BridgeTool import BridgeTool
from lnst.Slave.SlaveSecSocket import SlaveSecSocket, SecSocketException

# maximum time the server should block on select -- forces frequent Netlink
# checks
MAX_SERVER_HANG = 5

Devices = types.ModuleType("Devices")
Devices.__path__ = ["lnst.Devices"]

sys.modules["lnst.Devices"] = Devices

Tests = types.ModuleType("Tests")
Tests.__path__ = ["lnst.Tests"]

sys.modules["lnst.Tests"] = Tests

class SlaveMethods:
    '''
    Exported xmlrpc methods
    '''
    def __init__(self, job_context, log_ctl, net_namespaces,
                 server_handler, slave_config, slave_server):
        self._packet_captures = {}
        self._if_manager = None
        self._job_context = job_context
        self._log_ctl = log_ctl
        self._net_namespaces = net_namespaces
        self._server_handler = server_handler
        self._slave_server = slave_server
        self._slave_config = slave_config

        self._capture_files = {}
        self._copy_targets = {}
        self._copy_sources = {}
        self._system_config = {}

        self._cache = ResourceCache(slave_config.get_option("cache", "dir"),
                        slave_config.get_option("cache", "expiration_period"))

        self._dynamic_modules = {}
        self._dynamic_classes = {}

        self._bkp_nm_opt_val = slave_config.get_option("environment", "use_nm")

    def hello(self):
        logging.info("Recieved a controller connection.")

        slave_desc = {}
        if check_process_running("NetworkManager"):
            slave_desc["nm_running"] = True
        else:
            slave_desc["nm_running"] = False

        k_release, _ = exec_cmd("uname -r", False, False, False)
        r_release, _ = exec_cmd("cat /etc/redhat-release", False, False, False)
        slave_desc["kernel_release"] = k_release.strip()
        slave_desc["redhat_release"] = r_release.strip()
        slave_desc["lnst_version"] = lnst_version

        return ("hello", slave_desc)

    def set_recipe(self, recipe_name):
        self.machine_cleanup()
        self.restore_nm_option()

        self._cache.del_old_entries()
        self.reset_file_transfers()

        date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        self._log_ctl.set_recipe(recipe_name, expand=date)
        sleep(1)

        if check_process_running("NetworkManager"):
            logging.warning("=============================================")
            logging.warning("NetworkManager is running on a slave machine!")
            if self._slave_config.get_option("environment", "use_nm"):
                logging.warning("Support of NM is still experimental!")
            else:
                logging.warning("Usage of NM is disabled!")
            logging.warning("=============================================")

        for device in self._if_manager.get_devices():
            try:
                device.store_cleanup_data()
            except DeviceDisabled:
                pass

        return True

    def bye(self):
        self.restore_system_config()
        self._cache.del_old_entries()
        self.reset_file_transfers()
        self._remove_capture_files()
        return "bye"

    def map_device_class(self, cls_name, module_name):
        if cls_name in self._dynamic_classes:
            return

        module = self._dynamic_modules[module_name]
        cls = getattr(module, cls_name)

        self._dynamic_classes[cls_name] = cls

        setattr(Devices, cls_name, cls)

    def load_cached_module(self, module_name, res_hash):
        self._cache.renew_entry(res_hash)
        if module_name in self._dynamic_modules:
            return
        module_path = self._cache.get_path(res_hash)
        module = imp.load_source(module_name, module_path)
        self._dynamic_modules[module_name] = module

    def init_if_manager(self):
        self._if_manager = InterfaceManager(self._server_handler)
        for cls_name in dir(Devices):
            cls = getattr(Devices, cls_name)
            if isclass(cls):
                self._if_manager.add_device_class(cls_name, cls)

        self._if_manager.rescan_devices()
        self._server_handler.set_if_manager(self._if_manager)
        return True

    def dev_method(self, ifindex, name, args, kwargs):
        dev = self._if_manager.get_device(ifindex)
        method = getattr(dev, name)

        return method(*args, **kwargs)

    def dev_getattr(self, ifindex, name):
        dev = self._if_manager.get_device(ifindex)
        return getattr(dev, name)

    def dev_setattr(self, ifindex, name, value):
        dev = self._if_manager.get_device(ifindex)
        return setattr(dev, name, value)

    def get_devices(self):
        self._if_manager.rescan_devices()
        devices = self._if_manager.get_devices()
        result = {}
        for device in devices:
            result[device.ifindex] = device._get_if_data()
        return result

    def get_device(self, ifindex):
        self._if_manager.rescan_devices()
        device = self._if_manager.get_device(ifindex)
        if device:
            return device._get_if_data()
        else:
            return None

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

    def get_devices_by_params(self, params):
        devices = self._if_manager.get_devices()
        matched = []
        for dev in devices:
            dev_data = dev._get_if_data()
            entry = {"name": dev.get_name(),
                     "hwaddr": dev.get_hwaddr()}
            for key, value in params.iteritems():
                if key not in dev_data or dev_data[key] != value:
                    entry = None
                    break

            if entry is not None:
                matched.append(entry)
        return matched

    def destroy_devices(self):
        if self._if_manager is None:
            return

        devices = self._if_manager.get_devices()
        for dev in devices:
            try:
                dev.destroy()
            except (DeviceDisabled, DeviceDeleted, DeviceConfigValueError):
                pass
            self._if_manager.rescan_devices()

    # def add_route(self, if_id, dest):
        # dev = self._if_manager.get_mapped_device(if_id)
        # if dev is None:
            # logging.error("Device with id '%s' not found." % if_id)
            # return False
        # dev.add_route(dest)
        # return True

    # def del_route(self, if_id, dest):
        # dev = self._if_manager.get_mapped_device(if_id)
        # if dev is None:
            # logging.error("Device with id '%s' not found." % if_id)
            # return False
        # dev.del_route(dest)
        # return True

    def create_device(self, clsname, args=[], kwargs={}):
        dev =  self._if_manager.create_device(clsname, args, kwargs)
        if dev is None:
            raise Exception("Device creation failed")
        return {"ifindex": dev.ifindex, "name": dev.name}

    def start_packet_capture(self, filt):
        if not is_installed("tcpdump"):
            raise Exception("Can't start packet capture, tcpdump not available")

        files = {}
        for if_id, dev in self._if_manager.get_mapped_devices().iteritems():
            if dev.get_netns() != None:
                continue
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

        for ifindex, pcap in self._packet_captures.iteritems():
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

    def get_remaining_time(self, bg_id):
        cmd = self._command_context.get_cmd(bg_id)
        if "timeout" in cmd._command:
            cmd_timeout = cmd._command["timeout"]
        else:
            cmd_timeout = DEFAULT_TIMEOUT

        start_time = cmd._start_time
        current_time = time()

        remaining = cmd_timeout - (current_time - start_time)
        if remaining < 0:
            remaining = 0

        return int(remaining)

    def run_job(self, job):
        job_instance = Job(job, self._log_ctl)
        self._job_context.add_job(job_instance)

        res = job_instance.run()

        return res

    def kill_job(self, job_id, signal):
        job = self._job_context.get_job(job_id)

        if job is None:
            logging.error("No job %s found" % job_id)
            return False

        return job.kill(signal)

    def kill_jobs(self):
        logging.info("Killing all forked processes.")
        self._job_context.cleanup()
        return "Commands killed"

    def machine_cleanup(self):
        logging.info("Performing machine cleanup.")
        self._job_context.cleanup()

        self.restore_system_config()

        if self._if_manager is not None:
            self._if_manager.deconfigure_all()

        for netns in self._net_namespaces.keys():
            self.del_namespace(netns)
        self._net_namespaces = {}

        for cls_name, cls in self._dynamic_classes.items():
            delattr(Devices, cls_name)

        for module_name, module in self._dynamic_modules.items():
            del sys.modules[module_name]

        self._dynamic_classes = {}
        self._dynamic_modules = {}
        self._if_manager = None
        self._server_handler.set_if_manager(None)
        self._cache.del_old_entries()
        self._remove_capture_files()
        return True

    def has_resource(self, res_hash):
        if self._cache.query(res_hash):
            return True

        return False

    def add_resource_to_cache(self, res_type, local_path, name):
        if res_type == "file":
            self._cache.add_file_entry(local_path, name)
            return True
        else:
            raise Exception("Unknown resource type")

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

    def copy_part_to(self, filepath, data):
        if self._copy_targets[filepath]:
            self._copy_targets[filepath].write(data)
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
        data = self._copy_sources[filepath].read(buffsize)
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

    def enable_nm(self):
        logging.warning("====================================================")
        logging.warning("Enabling use of NetworkManager on controller request")
        logging.warning("====================================================")
        val = self._slave_config.get_option("environment", "use_nm")
        self._slave_config.set_option("environment", "use_nm", True)
        return val

    def disable_nm(self):
        logging.warning("=====================================================")
        logging.warning("Disabling use of NetworkManager on controller request")
        logging.warning("=====================================================")
        val = self._slave_config.get_option("environment", "use_nm")
        self._slave_config.set_option("environment", "use_nm", False)
        return val

    def restore_nm_option(self):
        val = self._slave_config.get_option("environment", "use_nm")
        if val == self._bkp_nm_opt_val:
            return val
        logging.warning("=========================================")
        logging.warning("Restoring use_nm option to original value")
        logging.warning("=========================================")
        self._slave_config.set_option("environment", "use_nm",
                                      self._bkp_nm_opt_val)
        return val

    def add_namespace(self, netns):
        if netns in self._net_namespaces:
            logging.debug("Network namespace %s already exists." % netns)
        else:
            logging.debug("Creating network namespace %s." % netns)
            read_pipe, write_pipe = multiprocessing.Pipe()
            pid = os.fork()
            if pid != 0:
                self._net_namespaces[netns] = {"pid": pid,
                                               "pipe": read_pipe}
                self._server_handler.add_netns(netns, read_pipe)

                result = self._slave_server.wait_for_result(netns)
                if result["result"] != True:
                    raise Exception("Namespace creation failed")

                return True
            elif pid == 0:
                self._slave_server.set_netns_sighandlers()
                #create new network namespace
                libc_name = ctypes.util.find_library("c")
                #from sched.h
                CLONE_NEWNET = 0x40000000
                CLONE_NEWNS = 0x00020000
                #based on ipnetns.c from the iproute2 project
                MNT_DETACH = 0x00000002
                MS_BIND = 4096
                MS_SLAVE = 1<<19
                MS_REC = 16384
                libc = ctypes.CDLL(libc_name)

                #based on ipnetns.c from the iproute2 project
                #bind to named namespace
                netns_path = "/var/run/netns/"
                if not os.path.exists(netns_path):
                    os.mkdir(netns_path, stat.S_IRWXU | stat.S_IRGRP |
                                         stat.S_IXGRP | stat.S_IROTH |
                                         stat.S_IXOTH)
                netns_path = netns_path + netns
                f = os.open(netns_path, os.O_RDONLY | os.O_CREAT | os.O_EXCL, 0)
                os.close(f)
                libc.unshare(CLONE_NEWNET)
                libc.mount("/proc/self/ns/net", netns_path, "none", MS_BIND, 0)

                #map network sysfs to new net
                libc.unshare(CLONE_NEWNS)
                libc.mount("", "/", "none", MS_SLAVE | MS_REC, 0)
                libc.umount2("/sys", MNT_DETACH)
                libc.mount(netns, "/sys", "sysfs", 0, 0)

                #set ctl socket to pipe to main netns
                self._server_handler.close_s_sock()
                self._server_handler.close_c_sock()
                self._server_handler.clear_connections()
                self._server_handler.clear_netns_connections()

                self._server_handler.set_netns(netns)
                self._server_handler.set_ctl_sock((write_pipe, "root_netns"))

                self._log_ctl.disable_logging()
                self._log_ctl.set_origin_name(netns)
                self._log_ctl.set_connection(write_pipe)

                self.init_if_manager()

                logging.debug("Created network namespace %s" % netns)
                return True
            else:
                raise Exception("Fork failed!")

    def del_namespace(self, netns):
        if netns not in self._net_namespaces:
            logging.debug("Network namespace %s doesn't exist." % netns)
            return False
        else:
            MNT_DETACH = 0x00000002
            libc_name = ctypes.util.find_library("c")
            libc = ctypes.CDLL(libc_name)
            netns_path = "/var/run/netns/" + netns

            netns_pid = self._net_namespaces[netns]["pid"]
            os.kill(netns_pid, signal.SIGUSR1)
            os.waitpid(netns_pid, 0)

            # Remove named namespace
            try:
                libc.umount2(netns_path, MNT_DETACH)
                os.unlink(netns_path)
            except:
                logging.warning("Unable to remove named namespace %s." % netns_path)

            logging.debug("Network namespace %s removed." % netns)

            self._net_namespaces[netns]["pipe"].close()
            self._server_handler.del_netns(netns)
            del self._net_namespaces[netns]
            return True

    def set_dev_netns(self, dev, dst):
        exec_cmd("ip link set %s netns %s" % (dev.name, dst))
        self._if_manager.untrack_device(dev)
        dev._deleted = True
        self._if_manager.rescan_devices()
        #TODO check if device appeared in the destination namespace
        return True

    # def return_if_netns(self, if_id):
        # device = self._if_manager.get_mapped_device(if_id)
        # if device.get_netns() == None:
            # dev_name = device.get_name()
            # ppid = os.getppid()
            # exec_cmd("ip link set %s netns %d" % (dev_name, ppid))
            # self._if_manager.unmap_if(if_id)
            # return True
        # else:
            # netns = device.get_netns()
            # msg = {"type": "command", "method_name": "return_if_netns",
                   # "args": [if_id]}
            # self._server_handler.send_data_to_netns(netns, msg)
            # result = self._slave_server.wait_for_result(netns)
            # if result["result"] != True:
                # raise Exception("Return from netns failed.")

            # device.set_netns(None)
            # return True

    def add_br_vlan(self, if_id, br_vlan_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.add_vlan(br_vlan_info)
        return True

    def del_br_vlan(self, if_id, br_vlan_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.del_vlan(br_vlan_info)
        return True

    def get_br_vlans(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        return brt.get_vlans()

    def add_br_fdb(self, if_id, br_fdb_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.add_fdb(br_fdb_info)
        return True

    def del_br_fdb(self, if_id, br_fdb_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.del_fdb(br_fdb_info)
        return True

    def get_br_fdbs(self, if_id):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        return brt.get_fdbs()

    def set_br_learning(self, if_id, br_learning_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_learning(br_learning_info)
        return True

    def set_br_learning_sync(self, if_id, br_learning_sync_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_learning_sync(br_learning_sync_info)
        return True

    def set_br_flooding(self, if_id, br_flooding_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_flooding(br_flooding_info)
        return True

    def set_br_state(self, if_id, br_state_info):
        dev = self._if_manager.get_mapped_device(if_id)
        if not dev:
            logging.error("Device with id '%s' not found." % if_id)
            return False
        brt = BridgeTool(dev.get_name())
        brt.set_state(br_state_info)
        return True

class ServerHandler(ConnectionHandler):
    def __init__(self, addr, slave_config):
        super(ServerHandler, self).__init__()
        self._netns_con_mapping = {}
        try:
            self._s_socket = socket.socket()
            self._s_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._s_socket.bind(addr)
            self._s_socket.listen(1)
        except socket.error as e:
            logging.error(e[1])
            exit(1)

        self._netns = None
        self._c_socket = None

        self._if_manager = None

        self._security = slave_config.get_section_values("security")

    def set_if_manager(self, if_manager):
        self._if_manager = if_manager

    def accept_connection(self):
        self._c_socket, addr = self._s_socket.accept()
        self._c_socket = (SlaveSecSocket(self._c_socket), addr[0])
        logging.info("Recieved connection from %s" % self._c_socket[1])

        try:
            self._c_socket[0].handshake(self._security)
        except:
            self.close_c_sock()
            raise

        self.add_connection(self._c_socket[1], self._c_socket[0])
        return self._c_socket

    def get_ctl_sock(self):
        try:
            return self._c_socket[0]
        except:
            return None

    def set_ctl_sock(self, sock):
        if self._c_socket != None:
            self.close_c_sock()
        self._c_socket = sock
        self.add_connection(self._c_socket[1], self._c_socket[0])

    def close_s_sock(self):
        self._s_socket.close()
        self._s_socket = None

    def close_c_sock(self):
        self._c_socket[0].close()
        self.remove_connection(self._c_socket[0])
        self._c_socket = None

    def check_connections(self, timeout=None):
        if self._if_manager is not None:
            self._if_manager.handle_netlink_msgs()
        msgs = super(ServerHandler, self).check_connections(timeout=timeout)
        return msgs

    def get_messages(self):
        messages = self.check_connections(timeout=MAX_SERVER_HANG)

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
        if self.get_connection(addr) == None:
            logging.info("Lost controller connection.")
            self.close_c_sock()
        return messages

    def get_messages_from_con(self, con_id):
        if con_id in self._connection_mapping:
            connection = self._connection_mapping[con_id]
        elif con_id in self._netns_con_mapping:
            connection = self._netns_con_mapping[con_id]
        else:
            raise Exception("Unknown connection id '%s'." % con_id)
        return self._check_connections([connection], timeout=None)

    def send_data_to_ctl(self, data):
        if self._c_socket != None:
            if self._netns != None:
                data = {"type": "from_netns",
                        "netns": self._netns,
                        "data": data}
            data = device_to_deviceref(data)
            return send_data(self._c_socket[0], data)
        else:
            return False

    def send_data_to_netns(self, netns, data):
        if netns not in self._netns_con_mapping:
            raise Exception("No network namespace '%s'!" % netns)
        else:
            netns_con = self._netns_con_mapping[netns]
            return send_data(netns_con, data)

    def clear_connections(self):
        super(ServerHandler, self).clear_connections()
        self._netns_con_mapping = {}

    def update_connections(self, connections):
        for key, connection in connections.iteritems():
            self.remove_connection_by_id(key)
            self.add_connection(key, connection)

    def set_netns(self, netns):
        self._netns = netns

    def add_netns(self, netns, connection):
        self._connections.append(connection)
        self._netns_con_mapping[netns] = connection

    def del_netns(self, netns):
        if netns in self._netns_con_mapping:
            connection = self._netns_con_mapping[netns]
            self._connections.remove(connection)
            del self._netns_con_mapping[netns]

    def clear_netns_connections(self):
        for netns, con in self._netns_con_mapping:
            self._connections.remove(con)
        self._netns_con_mapping = {}


def device_to_deviceref(obj):
    try:
        Device = Devices.Device
    except:
        return obj

    if isinstance(obj, Device):
        dev_ref = DeviceRef(obj.ifindex)
        return dev_ref
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            new_dict[key] = device_to_deviceref(value)
        return new_dict
    elif isinstance(obj, list):
        new_list = []
        for value in obj:
            new_list.append(device_to_deviceref(value))
        return new_list
    elif isinstance(obj, tuple):
        new_list = []
        for value in obj:
            new_list.append(device_to_deviceref(value))
        return tuple(new_list)
    else:
        return obj

def deviceref_to_device(if_manager, obj):
    if isinstance(obj, DeviceRef):
        dev = if_manager.get_device(obj.ifindex)
        return dev
    elif isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            new_dict[key] = deviceref_to_device(if_manager, value)
        return new_dict
    elif isinstance(obj, list):
        new_list = []
        for value in obj:
            new_list.append(deviceref_to_device(if_manager, value))
        return new_list
    elif isinstance(obj, tuple):
        new_list = []
        for value in obj:
            new_list.append(deviceref_to_device(if_manager, value))
        return tuple(new_list)
    elif isinstance(obj, Parameters):
        for param_name, param in obj:
            setattr(obj, param_name, deviceref_to_device(if_manager, param))
        return obj
    elif isinstance(obj, BaseTestModule):
        obj.params = deviceref_to_device(if_manager, obj.params)
        return obj
    else:
        return obj

class NetTestSlave:
    def __init__(self, log_ctl, slave_config):
        self._slave_config = slave_config
        die_when_parent_die()

        self._job_context = JobContext()
        port = slave_config.get_option("environment", "rpcport")
        logging.info("Using RPC port %d." % port)
        self._server_handler = ServerHandler(("", port), slave_config)

        self._net_namespaces = {}

        self._methods = SlaveMethods(self._job_context, log_ctl,
                                     self._net_namespaces,
                                     self._server_handler, slave_config,
                                     self)

        self.register_die_signal(signal.SIGHUP)
        self.register_die_signal(signal.SIGINT)
        self.register_die_signal(signal.SIGTERM)

        self._finished = False

        self._log_ctl = log_ctl

    def run(self):
        while not self._finished:
            if self._server_handler.get_ctl_sock() == None:
                self._log_ctl.cancel_connection()
                try:
                    logging.info("Waiting for connection.")
                    self._server_handler.accept_connection()
                except (socket.error, SecSocketException):
                    log_exc_traceback()
                    continue
                self._log_ctl.set_connection(self._server_handler.get_ctl_sock())

            msgs = self._server_handler.get_messages()

            for msg in msgs:
                self._process_msg(msg[1])

        self._methods.machine_cleanup()

    def wait_for_result(self, id):
        result = None
        while result == None:
            msgs = self._server_handler.get_messages_from_con(id)
            for msg in msgs:
                if msg[1]["type"] == "result":
                    result = msg[1]
                elif msg[1]["type"] == "from_netns" and\
                     msg[1]["data"]["type"] == "result":
                    result = msg[1]["data"]
                else:
                    self._process_msg(msg[1])
        return result

    def _process_msg(self, msg):
        if msg["type"] == "command":
            method = getattr(self._methods, msg["method_name"], None)
            if method != None:
                if_manager = self._methods._if_manager
                if if_manager is not None:
                    args = deviceref_to_device(if_manager, msg["args"])
                    kwargs = deviceref_to_device(if_manager, msg["kwargs"])
                else:
                    args = msg["args"]
                    kwargs = msg["kwargs"]

                try:
                    result = method(*args, **kwargs)
                except LnstError as e:
                    log_exc_traceback()
                    response = {"type": "exception", "Exception": e}

                    self._server_handler.send_data_to_ctl(response)
                    return

                response = {"type": "result", "result": result}
                response = device_to_deviceref(response)
                self._server_handler.send_data_to_ctl(response)
            else:
                err = LnstError("Method '%s' not supported." % msg["method_name"])
                response = {"type": "exception", "Exception": err}
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
            job = self._job_context.get_cmd(msg["job_id"])
            job.join()
            self._job_context.del_cmd(job)
            self._server_handler.send_data_to_ctl(msg)
        elif msg["type"] == "job_finished":
            job = self._job_context.get_job(msg["job_id"])
            job.join()

            job.set_finished(msg["result"])
            self._server_handler.send_data_to_ctl(msg)
        elif msg["type"] == "from_netns":
            self._server_handler.send_data_to_ctl(msg["data"])
        elif msg["type"] == "to_netns":
            netns = msg["netns"]
            try:
                self._server_handler.send_data_to_netns(netns, msg["data"])
            except LnstError as e:
                log_exc_traceback()
                response = {"type": "exception", "Exception": e}

                self._server_handler.send_data_to_ctl(response)
                return
        else:
            raise Exception("Recieved unknown command")

        pipes = self._job_context.get_parent_pipes()
        self._server_handler.update_connections(pipes)

    def register_die_signal(self, signum):
        signal.signal(signum, self._signal_die_handler)

    def _signal_die_handler(self, signum, frame):
        logging.info("Caught signal %d -> dying" % signum)
        self._finished = True

    def _parent_resend_signal_handler(self, signum, frame):
        logging.info("Caught signal %d -> resending to parent" % signum)
        os.kill(os.getppid(), signum)

    def set_netns_sighandlers(self):
        signal.signal(signal.SIGHUP, self._parent_resend_signal_handler)
        signal.signal(signal.SIGINT, self._parent_resend_signal_handler)
        signal.signal(signal.SIGTERM, self._parent_resend_signal_handler)
        signal.signal(signal.SIGUSR1, self._signal_die_handler)
