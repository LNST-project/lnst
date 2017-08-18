"""
This file containst classes for representing and handling
a Machine and an Interface in LNST

Copyright 2013 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
rpazdera@redhat.com (Radek Pazdera)
"""

import logging
import socket
import sys
import signal
from lnst.Common.Utils import sha256sum
from lnst.Common.Utils import check_process_running
from lnst.Common.TestModule import BaseTestModule
from lnst.Controller.Common import ControllerError
from lnst.Controller.CtlSecSocket import CtlSecSocket
from lnst.Devices import device_classes
from lnst.Devices.Device import Device
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Devices.VirtualDevice import VirtualDevice

# conditional support for libvirt
if check_process_running("libvirtd"):
    from lnst.Controller.VirtDomainCtl import VirtDomainCtl

class MachineError(ControllerError):
    pass

class PrefixMissingError(ControllerError):
    pass

class Machine(object):
    """ Slave machine abstraction

        A machine object represents a handle using which the controller can
        manipulate the machine. This includes tasks such as, configuration,
        deconfiguration, and running commands.
    """

    def __init__(self, m_id, hostname, msg_dispatcher, ctl_config,
                 libvirt_domain=None, rpcport=None, security=None):
        self._id = m_id
        self._hostname = hostname
        self._ctl_config = ctl_config
        self._slave_desc = None
        self._connection = None
        self._system_config = {}
        self._security = security
        self._security["identity"] = ctl_config.get_option("security",
                                                            "identity")
        self._security["privkey"] = ctl_config.get_option("security",
                                                           "privkey")

        self._domain_ctl = None
        self._network_bridges = None
        self._libvirt_domain = libvirt_domain
        if libvirt_domain:
            self._domain_ctl = VirtDomainCtl(libvirt_domain)

        if rpcport:
            self._port = rpcport
        else:
            self._port = ctl_config.get_option('environment', 'rpcport')

        self._msg_dispatcher = msg_dispatcher
        self._mac_pool = None

        self._interfaces = []
        self._namespaces = []
        self._bg_cmds = {}
        self._jobs = {}
        self._job_id_seq = 0

        self._device_database = {}
        self._tmp_device_database = []

        self._root_ns = None

        self._init_connection()

    def set_id(self, new_id):
        self._id = new_id

    def set_root_ns(self, ns):
        self._root_ns = ns

    def get_id(self):
        return self._id

    def get_configuration(self):
        configuration = {}
        configuration["id"] = self._id
        configuration["hostname"] = self._hostname
        configuration["kernel_release"] = self._slave_desc["kernel_release"]
        configuration["redhat_release"] = self._slave_desc["redhat_release"]

        configuration["interfaces"] = {}
        for dev in self._device_database.items():
            configuration["device_"+dev.name] = dev.get_config()
        return configuration

    def add_tmp_device(self, dev):
        self._tmp_device_database.append(dev)
        dev.host = self

    def remote_device_create(self, dev, netns=None):
        dev_clsname = dev._dev_cls.__name__
        dev_args = dev._dev_args
        dev_kwargs = dev._dev_kwargs
        ret = self.rpc_call("create_device", clsname=dev_clsname,
                                             args=dev_args,
                                             kwargs=dev_kwargs,
                                             netns=netns)
        dev._host = self
        dev.ifindex = ret["ifindex"]
        self._device_database[ret["ifindex"]] = dev

    def remote_device_set_netns(self, dev, dst, src):
        self.rpc_call("set_dev_netns", dev, dst, netns=src)

    def device_created(self, dev_data):
        ifindex = dev_data["ifindex"]
        if ifindex not in self._device_database:
            new_dev = None
            if len(self._tmp_device_database) > 0:
                for dev in self._tmp_device_database:
                    if dev._match_update_data(dev_data):
                        new_dev = dev
                        break

            if new_dev is None:
                new_dev = RemoteDevice(Device)
                new_dev.host = self
                new_dev.ifindex = ifindex
                new_dev.netns = self._root_ns
            else:
                self._tmp_device_database.remove(new_dev)

                new_dev.ifindex = dev_data["ifindex"]

            self._device_database[ifindex] = new_dev

    def device_delete(self, dev_data):
        if dev_data["ifindex"] in self._device_database:
            self._device_database[dev_data["ifindex"]].deleted = True

    def dev_db_get_ifindex(self, ifindex):
        if ifindex in self._device_database:
            return self._device_database[ifindex]
        else:
            return None

    def dev_db_get_name(self, dev_name):
        #TODO move these to Slave to optimize quering for each device
        for ifindex, dev in self._device_database.iteritems():
            if dev.get_name() == dev_name:
                return dev
        return None

    def get_dev_by_hwaddr(self, hwaddr):
        #TODO move these to Slave to optimize quering for each device
        for ifindex, dev in self._device_database.iteritems():
            if dev.hwaddr == hwaddr:
                return dev
        return None

    def rpc_call(self, method_name, *args, **kwargs):
        if "netns" in kwargs and kwargs["netns"] is not None:
            netns = kwargs["netns"]
            del kwargs["netns"]
            msg = {"type": "to_netns",
                   "netns": netns,
                   "data": {"type": "command",
                            "method_name": method_name,
                            "args": args,
                            "kwargs": kwargs}}
        else:
            if "netns" in kwargs:
                del kwargs["netns"]
            msg = {"type": "command",
                   "method_name": method_name,
                   "args": args,
                   "kwargs": kwargs}

        self._msg_dispatcher.send_message(self, msg)
        result = self._msg_dispatcher.wait_for_result(self)

        return result

    def _init_connection(self):
        """ Initialize the slave connection

        This will connect to the Slave, get it's description (should be
        usable for matching), and checks version compatibility
        """
        hostname = self._hostname
        port = self._port
        m_id = self._id

        logging.info("Connecting to RPC on machine %s (%s)", m_id, hostname)
        connection = CtlSecSocket(socket.create_connection((hostname, port)))
        connection.handshake(self._security)

        self._msg_dispatcher.add_slave(self, connection)

        hello, slave_desc = self.rpc_call("hello")
        if hello != "hello":
            msg = "Unable to establish RPC connection " \
                  "to machine %s, handshake failed!" % hostname
            raise MachineError(msg)

        slave_version = slave_desc["lnst_version"]
        slave_is_git = self.is_git_version(slave_version)
        ctl_version = self._ctl_config.version
        ctl_is_git = self.is_git_version(ctl_version)
        if slave_version != ctl_version:
            if ctl_is_git and slave_is_git:
                msg = "Controller and Slave '%s' git versions are different"\
                                                                    % hostname
                logging.warning(len(msg)*"=")
                logging.warning(msg)
                logging.warning(len(msg)*"=")
            else:
                msg = "Controller and Slave '%s' versions are not compatible!"\
                                                                    % hostname
                raise MachineError(msg)

        self._slave_desc = slave_desc

    def set_recipe(self, recipe_name):
        """ Reserves the machine for the specified recipe

        Also sends Device classes from the controller and initializes the
        InterfaceManager on the Slave and builds the device database.
        """
        self.rpc_call("set_recipe", recipe_name)
        self._send_device_classes()
        self.rpc_call("init_if_manager")

        devices = self.rpc_call("get_devices")
        for ifindex, dev in devices.items():
            remote_dev = RemoteDevice(Device)
            remote_dev.host = self
            remote_dev.ifindex = ifindex
            remote_dev.netns = self._root_ns

            self._device_database[ifindex] = remote_dev

    def _send_device_classes(self):
        classes = []
        for cls_name, cls in device_classes:
            classes.extend(reversed(self._get_base_classes(cls)))

        for cls in classes:
            if cls is object:
                continue
            module_name = cls.__module__
            module = sys.modules[module_name]
            filename = module.__file__

            if filename[-3:] == "pyc":
                filename = filename[:-1]

            res_hash = self.sync_resource(module_name, filename)
            self.rpc_call("load_cached_module", module_name, res_hash)

        for cls_name, cls in device_classes:
            module_name = cls.__module__
            self.rpc_call("map_device_class", cls_name, module_name)

    def is_git_version(self, version):
        try:
            int(version)
            return False
        except ValueError:
            return True

    def cleanup_devices(self):
        for netns in self._namespaces:
            self.rpc_call("destroy_devices", netns=netns)
        self.rpc_call("destroy_devices")

        for dev in self._device_database.values():
            if isinstance(dev, VirtualDevice):
                dev.destroy()
        self._device_database = {}

    def cleanup(self):
        """ Clean the machine up

            This is the counterpart of the configure() method. It will
            stop any still active commands on the machine, deconfigure
            all the interfaces that have been configured on the machine,
            and finalize and close the rpc connection to the machine.
        """
        #connection to the slave was closed
        if not self._msg_dispatcher.get_connection(self):
            return

        try:
            #dump statistics
            for dev in self._device_database.values():
                stats = dev.link_stats
                nsname = dev.netns.nsname if dev.netns.nsname else 'root'
                logging.debug("%s:%s:%s: RX:\t bytes: %d\t packets: %d\t dropped: %d" %
                              (nsname, self._id, dev.name,
                              stats["rx_bytes"], stats["rx_packets"], stats["rx_dropped"]))
                logging.debug("%s:%s:%s: TX:\t bytes: %d\t packets: %d\t dropped: %d" %
                              (nsname, self._id, dev.name,
                              stats["tx_bytes"], stats["tx_packets"], stats["tx_dropped"]))

            for netns in self._namespaces:
                self.rpc_call("kill_jobs", netns=netns)
            self.rpc_call("kill_jobs")

            self.restore_system_config()
            self.cleanup_devices()
            self.del_namespaces()
            # self.restore_nm_option()
            self.rpc_call("bye")
        except:
            #cleanup is only meaningful on dynamic interfaces, and should
            #always be called when deconfiguration happens- especially
            #when something on the slave breaks during deconfiguration
            self.cleanup_devices()
            raise

    def _timeout_handler(self, signum, frame):
        msg = "Timeout expired on machine %s" % self.get_id()
        raise MachineError(msg)

    def _get_base_classes(self, cls):
        new_bases = [cls] + list(cls.__bases__)
        bases = []
        while len(new_bases) != len(bases):
            bases = new_bases
            new_bases = list(bases)
            for b in bases:
                for bs in b.__bases__:
                    if bs not in new_bases:
                        new_bases.append(bs)
        return new_bases

    def run_job(self, job):
        job.id = self._job_id_seq
        self._job_id_seq += 1
        self._jobs[job.id] = job

        if job._type == "module":
            classes = [job._what]
            classes.extend(self._get_base_classes(job._what.__class__))

            for cls in reversed(classes):
                if cls is object or cls is BaseTestModule:
                    continue
                m_name = cls.__module__
                m = sys.modules[m_name]
                filename = m.__file__
                if filename[-3:] == "pyc":
                    filename = filename[:-1]

                res_hash = self.sync_resource(m_name, filename)

                self.rpc_call("load_cached_module", m_name, res_hash)

        logging.info("Host %s executing job %d: %s" %
                     (self._id, job.id, str(job)))
        if job._desc is not None:
            logging.info("Job description: %s" % job._desc)

        return self.rpc_call("run_job", job._to_dict(), netns=job.netns)

    def wait_for_job(self, job, timeout):
        res = True
        if job.id not in self._jobs:
            raise MachineError("No job '%s' running on Machine %s" %
                               (job.id, self._id))

        prev_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
        signal.alarm(timeout)

        try:
            if timeout > 0:
                logging.info("Waiting for Job %d on Host %s for %d seconds." %
                             (job.id, self._id, timeout))
            elif timeout == 0:
                logging.info("Waiting for Job %d on Host %s." %
                             (job.id, self._id))
            result = self._msg_dispatcher.wait_for_finish(self, job.id)
        except MachineError as exc:
            logging.error(str(exc))
            res = False

        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)

        return res

    def wait_for_tmp_devices(self, timeout):
        res = False
        prev_handler = signal.signal(signal.SIGALRM, self._timeout_handler)
        signal.alarm(timeout)

        try:
            if timeout > 0:
                logging.info("Waiting for Device creation Host %s for %d seconds." %
                             (self._id, timeout))
            elif timeout == 0:
                logging.info("Waiting for Device creation on Host %s." %
                             (self._id))

            while len(self._tmp_device_database) > 0:
                result = self._msg_dispatcher.handle_messages()
        except MachineError as exc:
            logging.error(str(exc))
            res = False

        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
        return res

    def job_finished(self, msg):
        job_id = msg["job_id"]
        job = self._jobs[job_id]
        job._res = msg["result"]

    def kill(self, job, signal):
        if job.id not in self._jobs:
            raise MachineError("No job '%s' running on Machine %s" %
                               (job.id(), self._id))
        return self.rpc_call("kill_job", job.id, signal, netns=job.netns)

    def get_hostname(self):
        """ Get hostname/ip of the machine

            This will return the hostname/ip of the machine's controller
            interface.
        """
        return self._hostname

    def get_libvirt_domain(self):
        return self._libvirt_domain

    def get_mac_pool(self):
        if self._mac_pool:
            return self._mac_pool
        else:
            raise MachineError("Mac pool not available.")

    def set_mac_pool(self, mac_pool):
        self._mac_pool = mac_pool

    def restore_system_config(self):
        self.rpc_call("restore_system_config")
        for netns in self._namespaces:
            self.rpc_call("restore_system_config", netns=netns)
        return True

    def set_network_bridges(self, bridges):
        self._network_bridges = bridges

    def get_network_bridges(self):
        if self._network_bridges != None:
            return self._network_bridges
        else:
            raise MachineError("Network bridges not available.")

    def get_domain_ctl(self):
        if not self._domain_ctl:
            raise MachineError("Machine '%s' is not virtual." % self.get_id())

        return self._domain_ctl

    def start_packet_capture(self):
        namespaces = set()
        for iface in self._interfaces:
            namespaces.add(iface.get_netns())

        tmp = {}
        for netns in namespaces:
            tmp.update(self.rpc_call("start_packet_capture", "", netns=netns))
        return tmp

    def stop_packet_capture(self):
        namespaces = set()
        for iface in self._interfaces:
            namespaces.add(iface.get_netns())

        for netns in namespaces:
            self.rpc_call("stop_packet_capture", netns=netns)

    def copy_file_to_machine(self, local_path, remote_path=None, netns=None):
        remote_path = self.rpc_call("start_copy_to", remote_path, netns=netns)

        f = open(local_path, "rb")

        while True:
            data = f.read(1024*1024) # 1MB buffer
            if len(data) == 0:
                break

            self.rpc_call("copy_part_to", remote_path, data, netns=netns)

        self.rpc_call("finish_copy_to", remote_path, netns=netns)

        return remote_path

    def copy_file_from_machine(self, remote_path, local_path):
        status = self.rpc_call("start_copy_from", remote_path)
        if not status:
            raise MachineError("The requested file cannot be transfered." \
                       "It does not exist on machine %s" % self.get_id())

        local_file = open(local_path, "wb")

        buf_size = 1024*1024 # 1MB buffer
        while True:
            data = self.rpc_call("copy_part_from", remote_path, buf_size)
            if data == "":
                break
            local_file.write(data)

        local_file.close()
        self.rpc_call("finish_copy_from", remote_path)

    def sync_resource(self, res_name, file_path):
        digest = sha256sum(file_path)

        if not self.rpc_call("has_resource", digest):
            msg = "Transfering %s to machine %s as '%s'" % (file_path,
                                                            self.get_id(),
                                                            res_name)
            logging.debug(msg)

            remote_path = self.copy_file_to_machine(file_path)
            self.rpc_call("add_resource_to_cache",
                           "file", remote_path, res_name)
        return digest

    # def enable_nm(self):
        # return self._rpc_call("enable_nm")

    # def disable_nm(self):
        # return self._rpc_call("disable_nm")

    # def restore_nm_option(self):
        # return self._rpc_call("restore_nm_option")

    def __str__(self):
        return "[Machine hostname(%s) libvirt_domain(%s) interfaces(%d)]" % \
               (self._hostname, self._libvirt_domain, len(self._interfaces))

    def add_netns(self, netns):
        self._namespaces.append(netns)
        return self.rpc_call("add_namespace", netns)

    def del_netns(self, netns):
        return self.rpc_call("del_namespace", netns)

    def del_namespaces(self):
        for netns in self._namespaces:
            self.del_netns(netns)
        self._namespaces = []
        return True

    def get_security(self):
        return self._security
