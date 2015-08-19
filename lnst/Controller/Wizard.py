"""
Wizard class for creating slave machine config files

Copyright 2015 Red Hat Inc.
Licensed under the GNU General Public Licence, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jprochaz@redhat.com (Jiri Prochazka)
"""

import socket
import sys
import time
import os
from lnst.Common.Utils import mkdir_p
from lnst.Common.Config import DefaultRPCPort
from lnst.Common.ConnectionHandler import send_data, recv_data
from xml.dom.minidom import getDOMImplementation

DefaultPoolDir = os.path.expanduser("~/.lnst/pool/")
PATH_IS_DIR_ACCESSIBLE = 0
PATH_IS_DIR_NOT_ACCESSIBLE = 1
PATH_DOES_NOT_EXIST = 2
PATH_NOT_DIR = 3


class Wizard:

    def interactive(self, pool_dir=None):
        """ Starts Wizard in an interactive mode
        @param pool_dir Path to pool directory (optional)
        """
        if pool_dir is None:
            pool_dir = self._query_pool_dir()
        else:
            rv = self._check_path(pool_dir)
            if rv == PATH_IS_DIR_ACCESSIBLE:
                print("Pool directory set to '%s'" % pool_dir)
            elif rv == PATH_DOES_NOT_EXIST:
                sys.stderr.write("Path '%s' does not exist\n" % pool_dir)
                pool_dir = self._query_pool_dir()
            elif rv == PATH_NOT_DIR:
                sys.stderr.write("Path '%s' exists but is not a directory\n"
                                 % pool_dir)
                pool_dir = self._query_pool_dir()
            elif rv == PATH_IS_DIR_NOT_ACCESSIBLE:
                sys.stderr.write("Directory '%s' is not writable\n" % pool_dir)
                pool_dir = self._query_pool_dir()

        while True:
            hostname = self._query_hostname()
            port = self._query_port()

            sock = self._get_connection(hostname, port)
            if sock is None:
                if self._query_continuation():
                    continue
                else:
                    break

            machine_interfaces = self._get_machine_interfaces(sock)
            sock.close()

            if machine_interfaces == {}:
                sys.stderr.write("No suitable interfaces found on the host "
                                 "'%s:%s'\n" % (hostname, port))
            elif machine_interfaces is not None:
                filename = self._query_filename(hostname)
                self._create_xml(machine_interfaces, hostname,
                                 port, pool_dir, filename, "interactive")
            if self._query_continuation():
                continue
            else:
                break

    def noninteractive(self, hostlist, pool_dir):
        """ Starts Wizard in noninteractive mode
        @param hostlist List of hosts (mandatory)
        @param pool_dir Path to pool_directory (optional)
        """
        if pool_dir is None:
            pool_dir = DefaultPoolDir

        rv = self._check_path(pool_dir)
        if rv == PATH_IS_DIR_ACCESSIBLE:
            print("Pool directory set to '%s'" % pool_dir)
        elif rv == PATH_DOES_NOT_EXIST:
            sys.stderr.write("Path '%s' does not exist\n" % pool_dir)
            pool_dir = self._create_dir(pool_dir)
            if pool_dir is None:
                sys.stderr.write("Pool wizard aborted\n")
                return
        elif rv == PATH_NOT_DIR:
            sys.stderr.write("Path '%s' exists but is not a directory\n"
                             % pool_dir)
            sys.stderr.write("Pool wizard aborted\n")
            return
        elif rv == PATH_IS_DIR_NOT_ACCESSIBLE:
            sys.stderr.write("Directory '%s' is not writable\n" % pool_dir)
            sys.stderr.write("Pool wizard aborted\n")
            return


        for host in hostlist:
            print("Processing host '%s'" % host)
            # Check if port was entered along with hostname
            if host.find(":") != -1:
                hostname = host.split(":")[0]
                if hostname == "":
                    msg = "'%s' does not contain valid hostname\n" % host
                    sys.stderr.write(msg)
                    sys.stderr.write("Skipping host '%s'\n" % host)
                    continue
                try:
                    port = int(host.split(":")[1])
                except:
                    port = DefaultRPCPort
                    msg = "Invalid port entered, "\
                          "using '%s' instead\n" % port
                    sys.stderr.write(msg)
            else:
                hostname = host
                port = DefaultRPCPort

            if not self._check_hostname(hostname):
                sys.stderr.write("Hostname '%s' is not translatable into a "
                                 "valid IP address\n" % hostname)
                sys.stderr.write("Skipping host '%s'\n" % host)
                continue

            sock = self._get_connection(hostname, port)
            if sock is None:
                sys.stderr.write("Skipping host '%s'\n" % host)
                continue

            machine_interfaces = self._get_machine_interfaces(sock)
            sock.close()

            if machine_interfaces is {}:
                sys.stderr.write("No suitable interfaces found on the host "
                                 "'%s:%s'\n" % (hostname, port))
                continue
            elif machine_interfaces is None:
                continue
            else:
                filename = hostname + ".xml"
                self._create_xml(machine_interfaces, hostname,
                                 port, pool_dir, filename, "noninteractive")

    def _check_hostname(self, hostname):
        """ Checks hostnames translatibility
        @param hostname Hostname which is checked whether it's valid
        @return True if valid hostname was entered, False otherwise
        """
        try:
            # Test if hostname is translatable into IP address
            socket.gethostbyname(hostname)
            return True
        except:
            return False

    def _check_path(self, pool_dir):
        """ Checks if path exists, is dir and is accessible by user
        @param pool_dir Path to checked directory
        @return True if user can write in entered directory, False otherwise
        """
        if not os.path.exists(pool_dir):
            return PATH_DOES_NOT_EXIST
        if os.path.isdir(pool_dir):
            if os.access(pool_dir, os.W_OK):
                return PATH_IS_DIR_ACCESSIBLE
            else:
                return PATH_IS_DIR_NOT_ACCESSIBLE
        else:
            return PATH_NOT_DIR

    def _create_dir(self, pool_dir):
        """ Creates specified directory
        @param pool_dir Directory to be created
        @return Path to dir which was created, None if no directory was created
        """
        try:
            mkdir_p(pool_dir)
            print("Dir '%s' has been created" % pool_dir)
            return pool_dir
        except:
            sys.stderr.write("Failed creating dir")
            return None

    def _create_xml(self, machine_interfaces, hostname,
                    port, pool_dir, filename, mode):
        """ Creates slave machine XML file
        @param machine_interfaces Dictionary with machine's interfaces
        @param hostname Hostname of the machine
        @param port Port on which LNST listens on the machine
        @param pool_dir Path to directory where XML file will be created
        @param filename Name of the XML file
        @param mode Mode in which wizard was started
        """

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

        interfaces_added = 0
        for iface in machine_interfaces.itervalues():
            if mode == "interactive":
                answer = raw_input("Do you want to add interface '%s' (%s) "
                                   "to the recipe? [Y/n]: " % (iface["name"],
                                                               iface["hwaddr"]))
            if mode == "noninteractive" or answer.lower() == "y"\
               or answer == "":
                interfaces_added += 1
                eth_el = doc.createElement("eth")
                eth_el.setAttribute("id", iface["name"])
                eth_el.setAttribute("label", "default_network")
                interfaces_el.appendChild(eth_el)
                params_el = doc.createElement("params")
                eth_el.appendChild(params_el)
                param_el = doc.createElement("param")
                param_el.setAttribute("name", "hwaddr")
                param_el.setAttribute("value", iface["hwaddr"])
                params_el.appendChild(param_el)
        if interfaces_added == 0:
            sys.stderr.write("You didn't add any interface, no file "
                             "'%s' will be created\n" % filename)
            return


        try:
            f = open(pool_dir + "/" + filename, "w")
            f.write(doc.toprettyxml())
            f.close()
        except:
            msg = "File '%s/%s' could not be opened or data written\n"\
                  % (pool_dir, filename)
            sys.stderr.write(msg)
            return

        print("File '%s' successfuly created" % filename)

    def _get_connection(self, hostname, port):
        """ Connects to machine
        @param hostname Hostname of the machine
        @param port Port of the machine
        @return Connected socket if connection was successful, None otherwise
        """
        try:
            sock = socket.create_connection((hostname, port))
            return sock
        except socket.error:
            sys.stderr.write("Connection to remote host '%s:%s' failed\n"
                             % (hostname, port))
            return None

    def _get_machine_interfaces(self, sock):
        """ Gets machine interfaces via RPC call
        @param sock Socket used for connecting to machine
        @return Dictionary with machine interfaces or None if RPC call fails
        """
        msg = {"type": "command", "method_name": "get_devices", "args": {}}
        if not send_data(sock, msg):
            sys.stderr.write("Could not send request to slave machine\n")
            return None

        while True:
            data = recv_data(sock)
            if data["type"] == "result":
                return data["result"]

    def _query_continuation(self):
        """ Queries user for adding next machine
        @return True if user wants to add another machine, False otherwise
        """
        answer = raw_input("Do you want to add another machine? [Y/n]: ")
        if answer.lower() == "y" or answer == "":
            return True
        else:
            return False

    def _query_dir_creation(self, pool_dir):
        """ Queries user for creating specified directory
        @return True if user wants to create the directory, False otherwise
        """
        answer = raw_input("Create dir '%s'? [Y/n]: " % pool_dir)
        if answer.lower() == 'y' or answer == "":
            return True
        else:
            return False

    def _query_filename(self, hostname):
        """ Queries user for name of the file
        @hostname Hostname of the machine which is used as default filename
        @return Name of the file with .xml extension
        """
        output_file = raw_input("Enter the name of the output .xml file "
                                "(without .xml, default is '%s.xml'): "
                                % hostname)
        if output_file == "":
            return hostname + ".xml"
        else:
            return output_file + ".xml"

    def _query_hostname(self):
        """ Queries user for hostname
        @return Valid (is translatable to an IP address) hostname
        """
        while True:
            hostname = raw_input("Enter hostname: ")
            if hostname == "":
                sys.stderr.write("No hostname entered\n")
                continue
            if self._check_hostname(hostname):
                return hostname
            else:
                sys.stderr.write("Hostname '%s' is not translatable into a "
                                 "valid IP address\n" % hostname)

    def _query_pool_dir(self):
        """ Queries user for pool directory
        @return Valid (is writable by user) path to directory
        """
        while True:
            pool_dir = raw_input("Enter path to a pool directory "
                                 "(default: '%s'): " % DefaultPoolDir)
            if pool_dir == "":
                pool_dir = DefaultPoolDir

            pool_dir = os.path.expanduser(pool_dir)
            rv = self._check_path(pool_dir)
            if rv == PATH_IS_DIR_ACCESSIBLE:
                print("Pool directory set to '%s'" % pool_dir)
                return pool_dir
            elif rv == PATH_DOES_NOT_EXIST:
                sys.stderr.write("Path '%s' does not exist\n"
                                 % pool_dir)
                if self._query_dir_creation(pool_dir):
                    created_dir = self._create_dir(pool_dir)
                    if created_dir is not None:
                        return created_dir

            elif rv == PATH_NOT_DIR:
                sys.stderr.write("Path '%s' exists but is not a directory\n"
                                 % pool_dir)
            elif rv == PATH_IS_DIR_NOT_ACCESSIBLE:
                sys.stderr.write("Directory '%s' is not writable\n"
                                 % pool_dir)

    def _query_port(self):
        """ Queries user for port
        @return Integer representing port
        """
        while True:
            port = raw_input("Enter port (default: %d): " % DefaultRPCPort)
            if port == "":
                return DefaultRPCPort
            else:
                try:
                    port = int(port)
                    return port
                except:
                    sys.stderr.write("Invalid port entered\n")
