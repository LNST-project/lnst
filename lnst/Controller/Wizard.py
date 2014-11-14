"""
Wizard class for creating machine pool .xml files

Copyright 2014 Red Hat Inc.
Licensed under the GNU General Public Licence, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jprochaz@redhat.com (Jiri Prochazka)
"""
import socket
import sys
import os
from lnst.Controller.Machine import Machine
from lnst.Controller.MessageDispatcherLite import MessageDispatcherLite
from lnst.Common.NetUtils import test_tcp_connection
from lnst.Common.Utils import mkdir_p
from lnst.Common.Config import DefaultRPCPort
from xml.dom.minidom import getDOMImplementation

class Wizard:
    def __init__(self):
        self._msg_dispatcher = MessageDispatcherLite()
        self._pool_dir = os.path.expanduser("~/.lnst/pool")

    def interactive(self):
        """
        Starts Wizard in interactive mode. Wizard requests hostname and port
        from user, tests connectivity to entered host, then he tries to connect
        and configure slave on host machine, and finally he requests list of
        ethernet interfaces in state DOWN. Then he writes them into .xml file
        named by user. User can choose which interfaces should be added to the
        .xml file.
        """

        pool_dir = raw_input("Enter path to pool directory "\
                             "(default: ~/.lnst/pool): ")
        if pool_dir != "":
            self._pool_dir = os.path.expanduser(pool_dir)
            print "Pool directory set to %s" % self._pool_dir

        while True:
            while True:
                hostname = raw_input("Enter hostname: ")
                try:
                # Tests if hostname is translatable into IP address
                    socket.gethostbyname(hostname)
                    break
                except:
                    sys.stderr.write("Hostname is not translatable into valid"\
                                     " IP address.\n")
                    continue
            while True:
                port = raw_input("Enter port(default: 9999): ")
                if port == "":
                    port = DefaultRPCPort
                try:
                    port = int(port)
                    break
                except:
                    sys.stderr.write("Invalid port.")
                    continue
            msg = self._get_suitable_interfaces(socket.gethostbyname(hostname),\
                                             port)
            if msg:
                self._write_to_xml(msg, hostname, port, "interactive")
            next_machine = raw_input("Do you want to add another machine? "\
                                     "[Y/n]: ")
            if next_machine.lower() == 'y' or next_machine == "":
                continue
            else:
                break
            return

    def noninteractive(self, hostlist):
        """
        Starts Wizard in noninteractive mode. Wizard gets list of hosts and
        ports as arguments. He tries to connect and get info about suitable
        interfaces for each of the hosts. Noninteractive mode does not prompt
        user about anything, it automatically adds all suitable interfaces into
        .xml file named the same as the hostname of the selected machine.
        """
        self._mode = "noninteractive"

        for host in hostlist:
            # Checks if port was entered along with hostname
            if host.find(":") != -1:
               hostname = host.split(':')[0]
               try:
                   port = int(host.split(':')[1])
               except:
                   port = DefaultRPCPort
            else:
                hostname = host
                port = DefaultRPCPort
            msg = self._get_suitable_interfaces(hostname, port)
            if not msg:
                continue
            self._write_to_xml(msg, hostname, port, "noninteractive")

    def _get_suitable_interfaces(self, hostname, port):
        """
        Calls all functions, which are used by both interactive and
        noninteractive mode to get list of suitable interfaces. The list is
        saved to variable msg.
        """
        if not test_tcp_connection(hostname, port):
            sys.stderr.write("Host destination '%s:%s' unreachable.\n"
                              % (hostname, port))
            return False
        if not self._connect_and_configure_machine(hostname, port):
            return False
        msg =  self._get_device_ifcs(hostname, port)
        self._msg_dispatcher.disconnect_slave(1)
        return msg

    def _get_device_ifcs(self, hostname, port):
        """
        Sends RPC call request to Slave to call function get_devices, which
        returns list of ethernet devices which are in state DOWN.
        """
        msg = self._machine._rpc_call("get_devices")
        if msg == {}:
            sys.stderr.write("No suitable interfaces found on the slave "\
                             "'%s:%s'.\n" % (hostname, port))
            return False
        return msg

    def _connect_and_configure_machine(self, hostname, port):
        """
        Connects to Slave and configures it
        """
        try:
            self._machine = Machine(1, hostname, None, port)
            self._machine.set_rpc(self._msg_dispatcher)
            self._machine.configure("MachinePoolWizard")
            return True
        except:
            sys.stderr.write("Remote machine '%s:%s' configuration failed!\n"
                              % (hostname, port))
            self._msg_dispatcher.disconnect_slave(1)
            return False

    def _write_to_xml(self, msg, hostname, port, mode):
        """
        Used for writing desired output into .xml file. In interactive mode,
        user is prompted for every interface, in noninteractive mode all
        interfaces are automatically added to the .xml file.
        """
        if mode == "interactive":
            output_file = raw_input("Enter the name of the output .xml file "\
                                    "(without .xml, default is hostname.xml): ")
        if mode == "noninteractive" or output_file == "":
            output_file = hostname

        impl = getDOMImplementation()
        doc = impl.createDocument(None, "slavemachine", None)
        top_el = doc.documentElement
        params_el = doc.createElement("params")
        top_el.appendChild(params_el)
        param_el = doc.createElement("param")
        param_el.setAttribute("name", "hostname")
        param_el.setAttribute("value", hostname)
        params_el.appendChild(param_el)
        interfaces_el = doc.createElement("interfaces")
        top_el.appendChild(interfaces_el)

        devices_added = 0
        for interface in msg.itervalues():
            if mode == 'interactive':
                answer = raw_input("Do you want to add interface '%s' (%s) "
                                   "to the recipe? [Y/n]" % (interface['name'],
                                                          interface['hwaddr']))
            if mode == "noninteractive" or answer.lower() == 'y'\
               or answer == "":
                devices_added += 1
                eth_el = doc.createElement("eth")
                eth_el.setAttribute("id", interface['name'])
                eth_el.setAttribute("label", "default_network")
                interfaces_el.appendChild(eth_el)
                params_el = doc.createElement("params")
                eth_el.appendChild(params_el)
                param_el = doc.createElement("param")
                param_el.setAttribute("name", "hwaddr")
                param_el.setAttribute("value", interface['hwaddr'])
                params_el.appendChild(param_el)
        if devices_added == 0:
            sys.stderr.write("You didn't add any interface, no file '%s.xml' "\
                  "will be created!\n" % output_file)
            return

        mkdir_p(self._pool_dir)

        try:
            f = open(self._pool_dir + "/" + output_file + ".xml", 'w')
            f.write(doc.toprettyxml())
            f.close()
        except:
            sys.stderr.write("File '%s.xml' could not be opened "\
                             "or data written." % output_file+"\n")
            raise WizardException()

        print "File '%s.xml' successfuly created." % output_file

class WizardException(Exception):
    pass
