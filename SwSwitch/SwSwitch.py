"""
This module defines SwSwitch class which operates software switch
and makes it configurable over xmlrpc

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import signal
import select, logging
from Common.Logs import Logs
from Common.XmlRpc import Server
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from NetConfig.NetConfig import NetConfig
from Common.Utils import die_when_parent_die
from NetConfig.NetConfigCommon import get_option

DefaultRPCPort = 9998

NOTE_EXTID = "external_id"
NOTE_VLANNAME = "vlan_name"
NOTE_VLANID = "vlan_id"
DEFAULT_VLAN = 1

class SwSwitchCtl:
    '''
    This class allows software switch control. Uses NetConfig to do
    the hard work of manipulating physical devices. Switch specific
    info is stored in "notes"
    '''

    def __init__(self, machine_config_xml):
        self._machine_config_xml = machine_config_xml
        self._nc = None
        self._reinit()

    def _reinit(self):
        if self._nc:
            self._nc.deconfigure_all()
        net_config = NetConfig(self._machine_config_xml)
        net_config.configure_all()

        self._nc = net_config
        self.vlan_add("default", DEFAULT_VLAN)

        dump = net_config.dump_config()
        for dev_id in dump:
            netdev = dump[dev_id]
            if netdev["type"] != "eth":
                continue
            net_config.set_notes(dev_id, {NOTE_EXTID: dev_id})
            self.port_vlan_add(dev_id, DEFAULT_VLAN, False)
        return True

    def __del__(self):
        self._nc.deconfigure_all()

    def _get_dev_id(self, dev_type, external_id=None, vlan_id=None,
                    vlan_name=None):
        '''
        Gets netdev id using one or many parameters
        '''
        dump = self._nc.dump_config()
        for dev_id in dump:
            netdev = dump[dev_id]
            if netdev["type"] == dev_type:
                if external_id:
                    if netdev["notes"][NOTE_EXTID] == external_id:
                        return dev_id
                if vlan_id:
                    if netdev["notes"][NOTE_VLANID] == vlan_id:
                        return dev_id
                if vlan_name:
                    if netdev["notes"][NOTE_VLANNAME] == vlan_name:
                        return dev_id
        return 0

    def _get_dev_tagged_vlans(self, dev_id):
        '''
        Gets vlan ids of all vlan the netdevice is part of
        '''
        vlans = []
        dump = self._nc.dump_config()
        for key in dump:
            netdev = dump[key]
            if (netdev["type"] == "vlan" and
                netdev["slaves"][0] == dev_id):
                vlans.append(int(get_option(netdev, "vlan_tci")))
        return vlans

    def _get_vlan_dev_id(self, real_dev_id, vlan_id):
        '''
        Gets vlan netdev id by given real netdev id and vlan id
        '''
        dump = self._nc.dump_config()
        for key in dump:
            netdev = dump[key]
            if (netdev["type"] == "vlan" and
                netdev["slaves"][0] == real_dev_id and
                int(get_option(netdev, "vlan_tci")) == vlan_id):
                return key

    def _get_vlan_real_dev_id(self, vlan_dev_id, vlan_id):
        '''
        Gets real netdev id by given vlan netdev id and vlan id
        '''
        dump = self._nc.dump_config()
        netdev = dump[vlan_dev_id]
        if (netdev["type"] == "vlan" and
            int(get_option(netdev, "vlan_tci")) == vlan_id):
            return netdev["slaves"][0]

    def list_ports(self):
        ports = []
        dump = self._nc.dump_config()
        for dev_id in dump:
            netdev = dump[dev_id]
            if netdev["type"] != "eth":
                continue
            notes = netdev["notes"]
            port = {"port": notes[NOTE_EXTID]}
            vlans = []
            if NOTE_VLANID in notes:
                vlans.append({"vlanid": notes[NOTE_VLANID], "tagged": False})
            tvlans = self._get_dev_tagged_vlans(dev_id)
            for tvlan in tvlans:
                vlans.append({"vlanid": tvlan, "tagged": True})
            port["vlans"] = vlans
            ports.append(port)
        return ports

    def _get_extid(self, dump, dev_id):
        return dump[dev_id]["notes"][NOTE_EXTID]

    def _get_vlan_ports(self, vlan_id):
        ports = []
        dump = self._nc.dump_config()
        for dev_id in dump:
            netdev = dump[dev_id]
            if (netdev["type"] == "eth" and
                NOTE_VLANID in netdev["notes"] and
                netdev["notes"][NOTE_VLANID] == vlan_id):
                port_id = self._get_extid(dump, dev_id)
                ports.append({"port": port_id, "tagged": False})
            elif netdev["type"] == "vlan":
                real_dev_id = self._get_vlan_real_dev_id(dev_id, vlan_id)
                if real_dev_id:
                    port_id = self._get_extid(dump, real_dev_id)
                    ports.append({"port": port_id, "tagged": True})
        return ports

    def list_vlans(self):
        vlans = []
        dump = self._nc.dump_config()
        for dev_id in dump:
            netdev = dump[dev_id]
            if netdev["type"] != "bridge":
                continue
            vlan_id =  netdev["notes"][NOTE_VLANID]
            vlan = {"vlanid": vlan_id, "ports": self._get_vlan_ports(vlan_id)}
            vlans.append(vlan)
        return vlans

    def vlan_add(self, name, vlan_id):
        logging.debug("Adding vlan id \"%d\"" % vlan_id)
        if self._get_dev_id("bridge", vlan_id=vlan_id):
            logging.error("Vlan id \"%d\" already exists" % vlan_id)
            return False
        br_dev_id = self._nc.netdev_add("bridge")
        self._nc.set_notes(br_dev_id, {NOTE_VLANID: vlan_id})
        self._nc.configure(br_dev_id)
        return True

    def vlan_del(self, vlan_id):
        logging.debug("Deleting vlan id \"%d\"" % vlan_id)
        if vlan_id == DEFAULT_VLAN:
            logging.error("cannot delete default vlan id \"%d\"" % DEFAULT_VLAN)
            return False
        br_dev_id = self._get_dev_id("bridge", vlan_id=vlan_id)
        if not br_dev_id:
            logging.error("Vlan id \"%d\" does not exist" % vlan_id)
            return False

        '''
        Remove ports in this vlan first
        '''
        ports = self._get_vlan_ports(vlan_id)
        for port in ports:
            self.port_vlan_del(port["port"], vlan_id, port["tagged"])

        self._nc.deconfigure(br_dev_id)
        self._nc.netdev_del(br_dev_id)
        return True

    class DevIdNotFound(Exception):
        pass

    def _get_dev_ids(self, port_id, vlan_id):
        br_dev_id = self._get_dev_id("bridge", vlan_id=vlan_id)
        if not br_dev_id:
            logging.error("Vlan id \"%d\" does not exist" % vlan_id)
            raise self.DevIdNotFound
        dev_id = self._get_dev_id("eth", external_id=port_id)
        if not br_dev_id:
            logging.error("Port \"%d\" does not exist" % vlan_id)
            raise self.DevIdNotFound
        return br_dev_id, dev_id

    def port_vlan_add(self, port_id, vlan_id, tagged):
        logging.debug("Adding port \"%d\", tagged \"%d\" to vlan id \"%d\""
                                        % (port_id, tagged, vlan_id))
        try:
            br_dev_id, dev_id = self._get_dev_ids(port_id, vlan_id)
        except self.DevIdNotFound:
            return False

        if tagged:
            if vlan_id in self._get_dev_tagged_vlans(dev_id):
                logging.error("Port \"%d\", is already tagged part of "
                              "vlan id \"%d\"" % (port_id, vlan_id))
                return False

            params = {"options": [("vlan_tci", vlan_id)],
                      "slaves": set([dev_id])}
            vlan_dev_id = self._nc.netdev_add("vlan", params=params)
            self._nc.set_notes(vlan_dev_id, {NOTE_VLANID: vlan_id})
            self._nc.configure(vlan_dev_id)
            self._nc.slave_add(br_dev_id, vlan_dev_id)
        else:
            notes = self._nc.get_notes(dev_id)
            if NOTE_VLANID in notes:
                '''
                In case when the port is already part of untagged vlan, remove
                it from this vlan first.
                '''
                self.port_vlan_del(port_id, notes[NOTE_VLANID], False)

            self._nc.slave_add(br_dev_id, dev_id)
            notes[NOTE_VLANID] = vlan_id

        return True

    def port_vlan_del(self, port_id, vlan_id, tagged):
        logging.debug("Removing port \"%d\", tagged \"%d\" from vlan id \"%d\""
                                        % (port_id, tagged, vlan_id))
        try:
            br_dev_id, dev_id = self._get_dev_ids(port_id, vlan_id)
        except self.DevIdNotFound:
            return False

        if tagged:
            if not vlan_id in self._get_dev_tagged_vlans(dev_id):
                logging.error("Port \"%d\", is not tagged part of "
                              "vlan id \"%d\"" % (port_id, vlan_id))
                return False

            vlan_dev_id = self._get_vlan_dev_id(dev_id, vlan_id)
            self._nc.slave_del(br_dev_id, vlan_dev_id)
            self._nc.deconfigure(vlan_dev_id)
            self._nc.netdev_del(vlan_dev_id)
        else:
            notes = self._nc.get_notes(dev_id)
            if not NOTE_VLANID in notes:
                logging.error("Port \"%d\" is not untagged part of "
                              "vlan id \"%d\"" % (port_id, vlan_id))
                return False

            self._nc.slave_del(br_dev_id, dev_id)
            del notes[NOTE_VLANID]

        return True

    def cleanup(self):
        logging.debug("Reinitializing")
        return self._reinit()

def int_it(val):
    try:
        num = int(val)
    except ValueError:
        num = 0
    return num

def bool_it(val):
    if isinstance(val, str):
        if re.match("^\s*(?i)(true)", val):
            return True
        elif re.match("^\s*(?i)(false)", val):
            return False
    return True if int_it(val) else False

class SwSwitchXMLRPC:
    '''
    Exported xmlrpc methods. Servers as a wrapper for SwSwitchCtl
    '''
    def __init__(self, sw_ctl):
        self._sw_ctl = sw_ctl

    def hello(self):
        return "hello"

    def set_logging(self, logger_address, port):
        """
        Server side setup logging to server side.

        @param logger_address: Address of running logger.
        """
        Logs.append_network_hadler(logger_address, port)
        return True

    def list_ports(self):
        return self._sw_ctl.list_ports()

    def list_vlans(self):
        return self._sw_ctl.list_vlans()

    def vlan_add(self, name, vlan_id):
        name = str(name)
        vlan_id = int_it(vlan_id)
        return self._sw_ctl.vlan_add(name, vlan_id)

    def vlan_del(self, vlan_id):
        vlan_id = int_it(vlan_id)
        return self._sw_ctl.vlan_del(vlan_id)

    def port_vlan_add(self, port_id, vlan_id, tagged):
        port_id = int_it(port_id)
        vlan_id = int_it(vlan_id)
        tagged = bool_it(tagged)
        return self._sw_ctl.port_vlan_add(port_id, vlan_id, tagged)

    def port_vlan_del(self, port_id, vlan_id, tagged):
        port_id = int_it(port_id)
        vlan_id = int_it(vlan_id)
        tagged = bool_it(tagged)
        return self._sw_ctl.port_vlan_del(port_id, vlan_id, tagged)

    def cleanup(self):
        return self._sw_ctl.cleanup()

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

class SwSwitch:
    def __init__(self, machine_config_xml, port = None):
        if not port:
            port = DefaultRPCPort

        sw_ctl = SwSwitchCtl(machine_config_xml)

        die_when_parent_die()

        server = MySimpleXMLRPCServer(("", port), SimpleXMLRPCRequestHandler,
                                      logRequests = False)
        server.register_die_signal(signal.SIGHUP)
        server.register_die_signal(signal.SIGINT)
        server.register_die_signal(signal.SIGTERM)
        server.register_instance(SwSwitchXMLRPC(sw_ctl))
        self._server = server

    def run(self):
        self._server.serve_forever_with_signal_check()
