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
from lnst.Common.Utils import sha256sum
from lnst.Common.Utils import check_process_running
from lnst.Common.Version import lnst_version
from lnst.Controller.Common import ControllerError
from lnst.Controller.CtlSecSocket import CtlSecSocket
from lnst.Controller.RecipeResults import JobStartResult, JobFinishResult, DeviceCreateResult, DeviceMethodCallResult, DeviceAttrSetResult, ResultType
from lnst.Controller.AgentProxyObject import AgentProxyObject
from lnst.Devices import device_classes
from lnst.Devices.Device import Device
from lnst.Devices.RemoteDevice import RemoteDevice
from lnst.Devices.LoopbackDevice import LoopbackDevice

# conditional support for libvirt
if check_process_running("libvirtd"):
    from lnst.Controller.VirtDomainCtl import VirtDomainCtl

class MachineError(ControllerError):
    pass

class PrefixMissingError(ControllerError):
    pass

class Machine(object):
    """ Agent machine abstraction

        A machine object represents a handle using which the controller can
        manipulate the machine. This includes tasks such as, configuration,
        deconfiguration, and running commands.
    """

    def __init__(self, m_id, hostname, msg_dispatcher, ctl_config,
                 libvirt_domain=None, rpcport=None, security=None, pool_params={}):
        self._id = m_id
        self._hostname = hostname
        self._mapped = False
        self._ctl_config = ctl_config
        self._agent_desc = None
        self._connection = None
        self._system_config = {}
        self._security = security
        self._security["identity"] = ctl_config.get_option("security",
                                                           "identity")
        self._security["privkey"] = ctl_config.get_option("security",
                                                           "privkey")

        self._pool_params = pool_params

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

        self._recipe = None
        self._mac_pool = None

        self._interfaces = []
        self._namespaces = {}
        self._bg_cmds = {}
        self._jobs = {}
        self._job_id_seq = 0

        self._device_database = {}
        self._tmp_device_database = []
        self._netns_moved_devices = {}

        self._initns = None

    def set_id(self, new_id):
        self._id = new_id

    def set_initns(self, ns):
        self._initns = ns

    def get_id(self):
        return self._id

    def set_mapped(self, new_value):
        self._mapped = new_value

    def get_mapped(self):
        return self._mapped

    def add_tmp_device(self, dev):
        self._tmp_device_database.append(dev)
        dev._machine = self

    def remote_device_create(self, dev, netns=None):
        dev_clsname = dev._dev_cls.__name__
        dev_args = dev._dev_args
        dev_kwargs = dev._dev_kwargs

        self._add_recipe_result(
            DeviceCreateResult(
                result=ResultType.PASS,
                device=dev,
            )
        )

        ret = self.rpc_call("create_device", clsname=dev_clsname,
                                             args=dev_args,
                                             kwargs=dev_kwargs,
                                             netns=netns)
        dev._machine = self
        dev.ifindex = ret["ifindex"]
        self._add_device_to_database(ret["ifindex"], dev, netns)

    def remote_device_set_netns(self, dev, dst, src):
        self._add_device_to_netns_moved_devices(dev, dst, src)
        self.rpc_call("set_dev_netns", dev, dst.name, netns=src)
        dev_clsname = dev._dev_cls.__name__
        dev_args = dev._dev_args
        dev_kwargs = dev._dev_kwargs

        if dev.peer_name:
            dev_kwargs['peer_name'] = dev.peer_name

        self.rpc_call("remap_device",
                dev.ifindex,
                clsname=dev_clsname,
                args=dev_args,
                kwargs=dev_kwargs,
                netns=dst)

    def _add_device_to_netns_moved_devices(self, dev, dst, src):
        del self._device_database[src][dev.ifindex]
        dev.enable_readonly_cache()
        self._netns_moved_devices[dev] = {
            "src": src,
            "dst": dst,
            "old_ifindex": dev.ifindex,
            "new_ifindex": None,
        }

    def remote_device_method(self, index, method_name, args, kwargs, netns):
        config_res = DeviceMethodCallResult(
            result=ResultType.PASS,
            device=self._get_device_from_database(index, netns),
            method_name=method_name,
            args=args,
            kwargs=kwargs,
        )

        try:
            res = self.rpc_call("dev_method", index, method_name, args, kwargs,
                                netns=netns)
        except:
            config_res.result = ResultType.FAIL
            raise
        finally:
            self._add_recipe_result(config_res)
        return res

    def remote_device_setattr(self, index, attr_name, value, netns):
        config_res = DeviceAttrSetResult(
            result=ResultType.PASS,
            device=self._get_device_from_database(index, netns),
            attr_name=attr_name,
            value=value,
            old_value=getattr(
                self._get_device_from_database(index, netns),
                attr_name
            ),
        )
        self._add_recipe_result(config_res)

        try:
            res = self.rpc_call("dev_setattr", index, attr_name, value, netns=netns)
        except:
            config_res.result = ResultType.FAIL
            raise
        return res

    def remote_device_getattr(self, index, attr_name, netns):
        return self.rpc_call("dev_getattr", index, attr_name, netns=netns)

    def device_created(self, dev_data, netns=None):
        ns_instance = self._get_netns_by_name(netns)
        ifindex = dev_data["ifindex"]
        if ifindex not in [idx for idx in self._device_database[ns_instance].keys()]:
            new_dev = None
            if len(self._tmp_device_database) > 0:
                for dev in self._tmp_device_database:
                    if dev._match_update_data(dev_data):
                        new_dev = dev
                        break

            moved_dev_match = [
                dev for dev, dev_details in self._netns_moved_devices.items()
                if dev_details["dst"] == ns_instance and dev_details["new_ifindex"] == ifindex
            ]

            netns_moved = False
            if len(moved_dev_match):
                new_dev = moved_dev_match[0]
                netns_moved = True

            if new_dev is None:
                if dev_data["driver"] == "loopback":
                    new_dev = RemoteDevice(LoopbackDevice)
                else:
                    new_dev = RemoteDevice(Device)
                new_dev._machine = self
                new_dev.ifindex = ifindex
                new_dev.netns = ns_instance
            else:
                if netns_moved:
                    del self._netns_moved_devices[new_dev]
                    new_dev.disable_readonly_cache()
                else:
                    self._tmp_device_database.remove(new_dev)
                    new_dev.ifindex = dev_data["ifindex"]

            self._add_device_to_database(ifindex, new_dev, ns_instance)

    def device_delete(self, dev_data, netns=None):
        ns_instance = self._get_netns_by_name(netns)
        dev_index = dev_data["ifindex"]

        if dev_index in self._device_database[ns_instance].keys():
            dev = self._device_database[ns_instance][dev_index]
            dev.deleted = True
            del self._device_database[ns_instance][dev_index]

    def device_netns_change(self, dev_data, netns=None):
        ns_instance = self._get_netns_by_name(netns)
        dev_index = dev_data["ifindex"]
        dev_new_index = dev_data["new_ifindex"]

        dev_match = [
            dev for dev, dev_details in self._netns_moved_devices.items()
            if dev_details["src"] == ns_instance and dev_index == dev_details["old_ifindex"]
        ]

        if len(dev_match) == 0:
            raise MachineError(
                "Device moved to ns {} with ifindex {} not found in cache".format(
                    netns,
                    dev_index
                )
            )

        self._netns_moved_devices[dev_match[0]]["new_ifindex"] = dev_new_index
        if dev_index in self._device_database[ns_instance].keys():
            del self._device_database[ns_instance][dev_index]

    def dev_db_get_ifindex(self, ifindex, netns=None):
        ns_instance = self._get_netns_by_name(netns)
        if ifindex in self._device_database[ns_instance].keys():
            return self._device_database[ns_instance][ifindex]
        else:
            return None

    def get_dev_by_hwaddr(self, hwaddr):
        #TODO move these to Agent to optimize quering for each device
        #TODO the method searches only the init namespace at the moment
        for dev in list(self._device_database[self._initns].values()):
            if dev.hwaddr == hwaddr:
                return dev
        return None

    def get_dev_by_ifname(self, ifname, netns=None):
        ns_instance = self._get_netns_by_name(netns)
        for dev in self._device_database[ns_instance].values():
            if dev.name == ifname:
                return dev
        return None

    def _find_device_in_any_namespace(self, ifindex, peer_ifindex=None):
        for ns in list(self._namespaces.keys()) + [None]:
            dev = self.dev_db_get_ifindex(ifindex, ns)
            if dev is None:
                continue
            if peer_ifindex:
                if dev.peer_if_id == peer_ifindex:
                    return dev
            else:
                return dev

        return None

    def rpc_call(self, method_name, *args, **kwargs):
        if kwargs.get("netns") in self._namespaces.values():
            netns = kwargs["netns"]
            del kwargs["netns"]
            msg = {"type": "to_netns",
                   "netns": netns.name,
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

        return self._msg_dispatcher.send_message(self, msg)

    def init_connection(self, timeout=None):
        """ Initialize the agent connection

        This will connect to the Agent, get it's description (should be
        usable for matching), and checks version compatibility
        """
        hostname = self._hostname
        port = self._port
        m_id = self._id

        logging.info("Connecting to RPC on machine %s (%s)", m_id, hostname)
        connection = CtlSecSocket(socket.create_connection((hostname, port),
                                                           timeout))
        connection.handshake(self._security)

        self._msg_dispatcher.add_agent(self, connection)

        hello, agent_desc = self.rpc_call("hello")
        if hello != "hello":
            msg = "Unable to establish RPC connection " \
                  "to machine %s, handshake failed!" % hostname
            raise MachineError(msg)

        agent_version = agent_desc["lnst_version"]

        if lnst_version != agent_version:
            if lnst_version.is_git_version:
                msg = ("Controller ({}) and Agent '{}' ({}) versions "
                       "are different".format(lnst_version, hostname,
                                              agent_version))
                logging.warning(len(msg)*"=")
                logging.warning(msg)
                logging.warning(len(msg)*"=")
            else:
                msg = ("Controller ({}) and Agent '{}' ({}) versions "
                       "are not compatible!".format(lnst_version, hostname,
                                                    agent_version))
                raise MachineError(msg)

        self._agent_desc = agent_desc

    def prepare_machine(self):
        self.rpc_call("prepare_machine")
        self._device_database = {self._initns: {}}
        self._send_device_classes()
        self.rpc_call("init_if_manager")

        devices = self.rpc_call("get_devices")
        for ifindex, dev in list(devices.items()):
            self.device_created(dev)

    def start_recipe(self, recipe):
        self._recipe = recipe
        recipe_name = recipe.__class__.__name__
        self.rpc_call("start_recipe", recipe_name)

    def stop_recipe(self):
        self._recipe = None

    def _add_recipe_result(self, result):
        if self._recipe:
            self._recipe.current_run.add_result(result)

    def _send_device_classes(self):
        for cls_name, cls in device_classes:
            self.send_class(cls)

        for cls_name, cls in device_classes:
            module_name = cls.__module__
            self.rpc_call("map_device_class", cls_name, module_name)

    def send_class(self, cls, netns=None):
        classes = [cls]
        classes.extend(self._get_base_classes(cls))

        for cls in reversed(classes):
            module_name = cls.__module__

            if module_name == "builtins":
                continue

            module = sys.modules[module_name]
            filename = module.__file__

            if filename[-3:] == "pyc":
                filename = filename[:-1]

            res_hash = self.sync_resource(module_name, filename, netns=netns)
            self.rpc_call("load_cached_module", module_name, res_hash, netns=netns)

    def is_git_version(self, version):
        try:
            int(version)
            return False
        except ValueError:
            return True

    def cleanup_devices(self):
        for netns in self._namespaces.values():
            self._set_readonly_cache_for_all_devices(netns)

        self._set_readonly_cache_for_all_devices(self._initns)

        for netns in self._namespaces.values():
            self.rpc_call("destroy_devices", netns=netns)

        self.rpc_call("destroy_devices")

    def _set_readonly_cache_for_device(self, ifindex, netns):
        try:
            dev = self._device_database[netns][ifindex]
        except KeyError:
            msg = "Device with index {} not found in netns({})".format(
                ifindex,
                netns.name
            )
            raise MachineError(msg)

        dev.enable_readonly_cache()

    def _set_readonly_cache_for_all_devices(self, netns):
        for dev in self._device_database[netns].values():
            dev.enable_readonly_cache()

    def cleanup(self):
        """ Clean the machine up

            This is the counterpart of the configure() method. It will
            stop any still active commands on the machine, deconfigure
            all the interfaces that have been configured on the machine,
            and finalize and close the rpc connection to the machine.
        """
        # connection to the agent was closed
        if not self._msg_dispatcher.get_connection(self):
            return

        try:
            for netns in self._namespaces.values():
                self.rpc_call("kill_jobs", netns=netns)
            self.rpc_call("kill_jobs")

            self.restore_system_config()
            self.cleanup_devices()
            self.del_namespaces()
            self.rpc_call("bye")
        except:
            # cleanup is only meaningful on dynamic interfaces, and should
            # always be called when deconfiguration happens- especially
            # when something on the agent breaks during deconfiguration
            self.cleanup_devices()
            raise

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

        if job.type == "module":
            # we need to send the class also into the root net namespace
            # so that the Agent instance can unpickle the message
            if job.netns is not None:
                self.send_class(job._what.__class__, netns=None)
            self.send_class(job._what.__class__, netns=job.netns)

        logging.debug("Host %s executing job %d: %s" %
                     (self._id, job.id, str(job)))
        logging.debug("Job.what = {}".format(repr(job.what)))
        if job._desc is not None:
            logging.info("Job description: %s" % job._desc)

        job_result = JobStartResult(job, ResultType.PASS)
        self._add_recipe_result(job_result)
        job_result.result = ResultType(
            self.rpc_call("run_job", job._to_dict(), netns=job.netns)
        )

        return job_result.result

    def wait_for_job(self, job, timeout):
        if job.id not in self._jobs:
            raise MachineError("No job '%s' running on Machine %s" %
                               (job.id, self._id))

        if timeout > 0:
            logging.debug("Waiting for Job %d on Host %s for %d seconds." %
                         (job.id, self._id, timeout))
        elif timeout == 0:
            logging.debug("Waiting for Job %d on Host %s." %
                         (job.id, self._id))

        def condition():
            return job.finished

        return self._msg_dispatcher.wait_for_condition(condition, timeout)

    def wait_for_tmp_devices(self, timeout):
        if timeout > 0:
            logging.info("Waiting for Device creation Host %s for %d seconds." %
                         (self._id, timeout))
        elif timeout == 0:
            logging.info("Waiting for Device creation on Host %s." %
                         (self._id))

        def condition():
            return len(self._tmp_device_database) <= 0

        return self._msg_dispatcher.wait_for_condition(condition, timeout)

    def job_finished(self, msg):
        job_id = msg["job_id"]
        job = self._jobs[job_id]
        job._res = msg["result"]
        self._add_recipe_result(JobFinishResult(job))

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
        for netns in self._namespaces.values():
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
            data: bytes = f.read(1024*1024) # 1MB buffer
            if not data:
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
            data: bytes = self.rpc_call("copy_part_from", remote_path, buf_size)
            if not data:
                break
            local_file.write(data)

        local_file.close()
        self.rpc_call("finish_copy_from", remote_path)

    def sync_resource(self, res_name, file_path, netns=None):
        digest = sha256sum(file_path)

        if not self.rpc_call("has_resource", digest, netns=netns):
            msg = "Transfering %s to machine %s as '%s'" % (file_path,
                                                            self.get_id(),
                                                            res_name)
            logging.debug(msg)

            remote_path = self.copy_file_to_machine(file_path, netns=netns)
            self.rpc_call("add_resource_to_cache",
                           "file", remote_path, res_name, netns=netns)
        return digest

    def init_remote_class(self, cls, *args, **kwargs):
        module_name = cls.__module__
        cls_name = cls.__name__
        obj_ref = self.rpc_call("init_cls", cls_name, module_name, args, kwargs)

        return AgentProxyObject(self, cls, obj_ref)

    def __str__(self):
        return "[Machine hostname(%s) libvirt_domain(%s) interfaces(%d)]" % \
               (self._hostname, self._libvirt_domain, len(self._interfaces))

    def add_netns(self, netns):
        self._namespaces[netns.name] = netns
        self._device_database[netns] = {}
        return self.rpc_call("add_namespace", netns.name)

    def del_netns(self, netns):
        return self.rpc_call("del_namespace", netns.name)

    def del_namespaces(self):
        for netns in self._namespaces.values():
            self.del_netns(netns)
        self._namespaces = {}
        return True

    def get_security(self):
        return self._security

    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove things that can't be pickled
        state['_msg_dispatcher'] = None
        if self.get_libvirt_domain():
            state['_domain_ctl'] = None
        return state

    def _get_netns_by_name(self, netns):
        if netns is None:
            return self._initns
        else:
            try:
                return self._namespaces[netns]
            except KeyError:
                raise MachineError("No network namespace with name {}".format(
                    netns)
                )

    def _add_device_to_database(self, ifindex, dev, netns=None):
        if not netns in self._device_database:
            self._device_database[netns] = {}

        self._device_database[netns][ifindex] = dev

    def _get_device_from_database(self, ifindex, netns=None):
        try:
            dev = self._device_database[netns][ifindex]
        except:
            raise MachineError(
                "No device with ifindex {} in netns {} device database".format(
                    ifindex, netns
                    )
                )

        return dev
