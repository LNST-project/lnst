"""
Wizard class for creating slave machine config files

Copyright 2015 Red Hat Inc.
Licensed under the GNU General Public Licence, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jprochaz@redhat.com (Jiri Prochazka)
"""

try:
    import libvirt
    LIBVIRT_SUPPORT = True
except ImportError:
    LIBVIRT_SUPPORT = False
import socket
import sys
import os
from lnst.Common.Utils import mkdir_p, check_process_running
from lnst.Common.Config import DefaultRPCPort
from lnst.Common.ConnectionHandler import send_data, recv_data
from lnst.Controller.CtlSecSocket import CtlSecSocket
from lnst.Common.SecureSocket import SecSocketException
from xml.dom.minidom import getDOMImplementation
from lxml import etree

DefaultPoolDir = os.path.expanduser("~/.lnst/pool/")
PATH_IS_DIR_ACCESSIBLE = 0
PATH_IS_DIR_NOT_ACCESSIBLE = 1
PATH_DOES_NOT_EXIST = 2
PATH_NOT_DIR = 3


class Wizard:
    def interactive(self, hostlist=None, pool_dir=None):
        """ Starts Wizard in an interactive mode
        @param pool_dir Path to pool directory (optional)
        """
        pool_dir = self._check_and_query_pool_dir(pool_dir)

        if hostlist is not None:
            for host in hostlist:
                hostname, port = self._parse_host(host)
                if hostname == -1:
                    continue

                sec_params = {"auth_type": "none"}
                sock = self._get_connection(hostname, port, sec_params)

                if sock is None:
                    continue
                machine_interfaces = self._get_machine_interfaces(sock)
                sock.close()

                if machine_interfaces == []:
                    sys.stderr.write("No suitable interfaces found on the host "
                                     "'%s:%s'\n" % (hostname, port))
                elif machine_interfaces is not None:
                    filename = self._query_filename(hostname)
                    self._create_xml(machine_interfaces=machine_interfaces,
                                     hostname=hostname, pool_dir=pool_dir,
                                     filename=filename, port=port,
                                     mode="interactive")

            return

        while True:
            hostname = self._query_hostname()
            port = self._query_port()
            sec_params = self._query_sec_params(hostname)

            sock = self._get_connection(hostname, port, sec_params)
            if sock is None:
                if self._query_continuation():
                    continue
                else:
                    break

            machine_interfaces = self._get_machine_interfaces(sock)
            sock.close()

            if machine_interfaces == []:
                sys.stderr.write("No suitable interfaces found on the host "
                                 "'%s:%s'\n" % (hostname, port))
            elif machine_interfaces is not None:
                filename = self._query_filename(hostname)
                self._create_xml(machine_interfaces=machine_interfaces,
                                 hostname=hostname, pool_dir=pool_dir,
                                 filename=filename, port=port,
                                 mode="interactive", sec_params=sec_params)

            if self._query_continuation():
                continue
            else:
                break

    def noninteractive(self, hostlist, pool_dir=DefaultPoolDir):
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
            hostname, port = self._parse_host(host)
            if hostname == -1:
                continue

            if not self._check_hostname(hostname):
                sys.stderr.write("Hostname '%s' is not translatable into a "
                                 "valid IP address\n" % hostname)
                sys.stderr.write("Skipping host '%s'\n" % host)
                continue

            sec_params = {"auth_type": "none"}
            sock = self._get_connection(hostname, port, sec_params)
            if sock is None:
                sys.stderr.write("Skipping host '%s'\n" % host)
                continue

            machine_interfaces = self._get_machine_interfaces(sock)
            sock.close()

            if machine_interfaces is []:
                sys.stderr.write("No suitable interfaces found on the host "
                                 "'%s:%s'\n" % (hostname, port))
                continue
            elif machine_interfaces is None:
                continue
            else:
                filename = hostname + ".xml"
                self._create_xml(machine_interfaces=machine_interfaces,
                                 hostname=hostname, pool_dir=pool_dir,
                                 filename=filename, port=port,
                                 mode="noninteractive")

    def virtual(self, pool_dir=None):
        """ Starts Wizard in a virtual mode
        @param pool_dir Path to pool directory (optional)
        """

        print("WARNING: For LNST Pool Wizard to work with virtual guests, "
              "several conditions have to be met: \n"
              "\t1) Guests must be running under libvirt and QEMU\n"
              "\t2) Guests must be in \"default\" network and have an IP "
              "address from DHCP in that network")

        if not LIBVIRT_SUPPORT:
            sys.stderr.write("Missing package libvirt-python, "
                             "aborting wizard\n")
            return

        if not check_process_running("libvirtd"):
            sys.stderr.write("libvirtd is not running, aborting wizard\n")
            return

        pool_dir = self._check_and_query_pool_dir(pool_dir)

        conn = libvirt.openReadOnly("qemu:///system")

        if conn is None:
            sys.stderr.write("Failed to open connection to hypervisor, "
                             "aborting wizard\n")
            return

        while True:
            libvirt_domain, hostname = self._query_libvirt_domain(conn)
            if hostname is None or libvirt_domain is None:
                return
            sec_params = self._query_sec_params(hostname)
            filename = self._query_filename(libvirt_domain)

            self._create_xml(hostname=hostname, pool_dir=pool_dir,
                             filename=filename, mode="virtual",
                             libvirt_domain=libvirt_domain,
                             sec_params=sec_params)

            if self._query_continuation():
                continue
            else:
                break

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

    def _check_and_query_pool_dir(self, pool_dir):
        """ Queries user for pool directory
        @param pool_dir Optional pool_dir which will be checked and used if OK
        @return Valid (is writable by user) path to directory
        """
        while True:
            if pool_dir is None:
                pool_dir = eval(input("Enter path to a pool directory "
                                     "(default: '%s'): " % DefaultPoolDir))
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
            pool_dir = None

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
            sys.stderr.write("Failed creating dir\n")
            return None

    def _create_xml(self, machine_interfaces=None, hostname=None,
                    pool_dir=None, filename=None, mode=None,
                    port=None, libvirt_domain=None, sec_params=None):
        """ Creates slave machine XML file
        @param machine_interfaces List of machine's interfaces
        @param hostname Hostname of the machine
        @param pool_dir Path to directory where XML file will be created
        @param filename Name of the XML file
        @param mode Mode in which wizard was started
        @param libvirt_domain Libvirt domain of virtual host
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
        if port is not None:
            param_el = doc.createElement("param")
            param_el.setAttribute("name", "rpc_port")
            param_el.setAttribute("value", str(port))
            params_el.appendChild(param_el)
        if mode == "virtual":
            param_el = doc.createElement("param")
            param_el.setAttribute("name", "libvirt_domain")
            param_el.setAttribute("value", libvirt_domain)
            params_el.appendChild(param_el)
        else:
            interfaces_el = doc.createElement("interfaces")
            top_el.appendChild(interfaces_el)

            interfaces_added = 0
            for iface in machine_interfaces:
                if mode == "interactive":
                    msg = "Do you want to add interface '%s' (%s) to the "\
                          "recipe? [Y/n]: " % (iface["name"], iface["hwaddr"])
                    answer = eval(input(msg))
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

        if sec_params:
            security_el = doc.createElement("security")
            top_el.appendChild(security_el)

            auth_type_el = doc.createElement("auth_type")
            security_el.appendChild(auth_type_el)

            auth_type_text = doc.createTextNode(sec_params["auth_type"])
            auth_type_el.appendChild(auth_type_text)

            if sec_params["auth_type"] is "password":
                password_el = doc.createElement("auth_passwd")
                security_el.appendChild(password_el)

                password_text = doc.createTextNode(sec_params["auth_password"])
                password_el.appendChild(password_text)
            elif sec_params["auth_type"] is "pubkey":
                pubkey_el = doc.createElement("pubkey_path")
                security_el.appendChild(pubkey_el)

                pubkey_text = doc.createTextNode(sec_params["srv_pubkey_path"])
                pubkey_el.appendChild(pubkey_text)

        if self._write_to_file(pool_dir, filename, doc):
            print("File '%s/%s' successfuly created." % (pool_dir, filename))
        else:
            sys.stderr.write("File '%s/%s' could not be opened "
                             "or data written.\n" % (pool_dir, filename))

    def _get_connection(self, hostname, port, sec_params):
        """ Connects to machine
        @param hostname Hostname of the machine
        @param port Port of the machine
        @return Connected socket if connection was successful, None otherwise
        """
        try:
            sock = socket.create_connection((hostname, port))
            ret = CtlSecSocket(sock)
            ret.handshake(sec_params)
            return ret
        except SecSocketException:
            sys.stderr.write("Couldn't connect to host %s:%s, because "\
                             "security negotiation failed.\n" %
                             (hostname, port))
            return None
        except socket.error:
            sys.stderr.write("Connection to remote host '%s:%s' failed\n"
                             % (hostname, port))
            return None

    def _get_machine_interfaces(self, sock):
        """ Gets machine interfaces via RPC call
        @param sock Socket used for connecting to machine
        @return Dictionary with machine interfaces or None if RPC call fails
        """
        msg = {"type": "command",
               "method_name": "get_devices_by_params",
               "args": [{"ifi_type": 1, "state": "DOWN"}]}
        if not send_data(sock, msg):
            sys.stderr.write("Could not send request to slave machine\n")
            return None

        while True:
            data = recv_data(sock)
            if data["type"] == "result":
                return data["result"]

    def _parse_host(self, host):
        """ Parses hostname:port string
        @param host String where hostname and optionally port is stored
        @return touple with string hostname and int port
        """
        if host.find(":") != -1:
            hostname = host.split(":")[0]
            if hostname == "":
                msg = "'%s' does not contain valid hostname\n" % host
                sys.stderr.write(msg)
                sys.stderr.write("Skipping host '%s'\n" % host)
                return -1, -1
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

        return hostname, port

    def _query_continuation(self):
        """ Queries user for adding next machine
        @return True if user wants to add another machine, False otherwise
        """
        answer = eval(input("Do you want to add another machine? [Y/n]: "))
        if answer.lower() == "y" or answer == "":
            return True
        else:
            return False

    def _query_dir_creation(self, pool_dir):
        """ Queries user for creating specified directory
        @return True if user wants to create the directory, False otherwise
        """
        answer = eval(input("Create dir '%s'? [Y/n]: " % pool_dir))
        if answer.lower() == 'y' or answer == "":
            return True
        else:
            return False

    def _query_filename(self, hostname):
        """ Queries user for name of the file
        @hostname Hostname of the machine which is used as default filename
        @return Name of the file with .xml extension
        """
        output_file = eval(input("Enter the name of the output .xml file "
                                "(without .xml, default is '%s.xml'): "
                                % hostname))
        if output_file == "":
            return hostname + ".xml"
        else:
            return output_file + ".xml"

    def _query_hostname(self):
        """ Queries user for hostname
        @return Valid (is translatable to an IP address) hostname
        """
        while True:
            hostname = eval(input("Enter hostname: "))
            if hostname == "":
                sys.stderr.write("No hostname entered\n")
                continue
            if self._check_hostname(hostname):
                return hostname
            else:
                sys.stderr.write("Hostname '%s' is not translatable into a "
                                 "valid IP address\n" % hostname)

    def _query_libvirt_domain(self, conn):
        """ Queries user for libvirt_domain
        @note Virtual host must be running under libvirt
              and has to have an IP from "default" network
              DHCP server
        @param conn libvirt connection to hypervisor
        @return Tuple of string representing libvirt_domain of the hosthost and
                string representing hostname of the host
        """
        while True:
            libvirt_domain = eval(input("Enter libvirt domain "
                                       "of virtual host: "))
            if libvirt_domain == "":
                sys.stderr.write("No domain entered\n")
                continue
            try:
                guest = conn.lookupByName(libvirt_domain)
            except:
                continue

            guestxml = etree.fromstring(guest.XMLDesc())

            macs = list()
            for mac in guestxml.findall(".//interface/source[@network='default']/../mac"):
                macs.append(mac.get('address'))

            guest_ip = None
            try:
                for lease in conn.networkLookupByName("default").DHCPLeases():
                    if lease['mac'] in macs:
                        guest_ip = lease['ipaddr']
                        break
            except:
                sys.stderr.write("Failed getting DHCPLeases from hypervisor\n")

            if guest_ip == None:
                sys.stderr.write("Couldn't find any IP associated with "
                                 "libvirt_domain '%s'\n" % libvirt_domain)
            else:
                return libvirt_domain, lease['ipaddr']

            hostname = self._query_hostname()
            return libvirt_domain, hostname

    def _query_port(self):
        """ Queries user for port
        @return Integer representing port
        """
        while True:
            port = eval(input("Enter port (default: %d): " % DefaultRPCPort))
            if port == "":
                return DefaultRPCPort
            else:
                try:
                    port = int(port)
                    return port
                except:
                    sys.stderr.write("Invalid port entered\n")

    def _query_sec_params(self, hostname):
        """ Queries user for security parameters of the connection
        @return Dictionary with the security parameters
        """
        while True:
            auth_type = eval(input("Enter authentication type (default: none): "))
            if auth_type == "":
                auth_type = "none"
            elif auth_type not in ["none", "no-auth", "password",
                                   "pubkey", "ssh"]:
                sys.stderr.write("Invalid authentication type.")
                continue
            break
        if auth_type == "none":
            return {"auth_type": "none"}
        elif auth_type == "no-auth":
            return {"auth_type": "no-auth"}
        elif auth_type == "ssh":
            return {"auth_type": "ssh"}
        elif auth_type == "password":
            while True:
                password = eval(input("Enter password: "))
                if password == "":
                    sys.stderr.write("Invalid password.")
                    continue
                break
            return {"auth_type": "password",
                    "auth_passwd": password}
        elif auth_type == "pubkey":
            while True:
                identity = eval(input("Enter identity: "))
                if identity == "":
                    sys.stderr.write("Invalid identity.")
                    continue
                break
            while True:
                privkey = eval(input("Enter path to Ctl private key: "))
                if privkey == "" or not os.path.isfile(privkey):
                    sys.stderr.write("Invalid path to private key.")
                    continue
                break
            while True:
                srv_pubkey_path = eval(input("Enter path to Slave public key: "))
                if srv_pubkey_path == "" or not os.path.isfile(srv_pubkey_path):
                    sys.stderr.write("Invalid path to public key.")
                    continue
                break
            return {"auth_type": "pubkey",
                    "identity": identity,
                    "privkey": privkey,
                    "srv_pubkey_path": srv_pubkey_path}

    def _write_to_file(self, pool_dir, filename, doc):
        """ Writes contents of XML to a file
        @param pool_dir Path to directory where the file will be created
        @param filename Name of the created file
        @param doc Contents of XML file
        @return True if file was successfuly written, False otherwise
        """
        try:
            f = open(pool_dir + "/" + filename, "w")
            f.write(doc.toprettyxml())
            f.close()
            return True
        except:
            return False
