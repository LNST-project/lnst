#! /usr/bin/env python
"""
Netconfig tool

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

import getopt
import sys
import logging
import re
import os
from pprint import pprint
from NetConfig.NetConfig import NetConfig
from NetConfig.NetConfigDevice import NetConfigDeviceAllCleanup
from NetConfig.NetConfigDevNames import NetConfigDevNames
from NetTest.NetTestParse import NetConfigParse
from NetTest.NetTestParse import NetMachineConfigParse
from Common.XmlProcessing import XmlDomTreeInit
from Common.Logs import Logs

def usage():
    """
    Print usage of this app
    """
    print "Usage: netconfig.py [OPTION...] ACTION"
    print ""
    print "ACTION = [up | down | dump | cleanup | test]"
    print ""
    print "  -d, --debug                             emit debugging messages"
    print "  -h, --help                              print this message"
    print "  -c, --config=FILE                       use this net configuration file"
    print "  -m, --machine-config=FILE               use this machine configuration file"
    sys.exit()

def prepare_machine_config(machine_file):
    tree_init = XmlDomTreeInit()
    dom = tree_init.parse_file(machine_file)
    machine_dom = dom.getElementsByTagName("netmachineconfig")[0]

    data = {"info":{}, "netdevices": {}, "netconfig": {}}

    machine_parse = NetMachineConfigParse()
    machine_parse.disable_events()
    machine_parse.set_recipe(data)
    machine_parse.set_machine(0, data)
    machine_parse.parse(machine_dom)

    return data

def prepare_netconfig(machine_file, config_file):
    tree_init = XmlDomTreeInit()
    data = prepare_machine_config(machine_file)

    dom = tree_init.parse_file(config_file)
    config_dom = dom.getElementsByTagName("netconfig")[0]

    config_parse = NetConfigParse()
    config_parse.disable_events()
    config_parse.set_recipe(data)
    config_parse.set_machine(0, data)
    config_parse.parse(config_dom)

    netconfig = NetConfig()
    for key, entry in data["netconfig"].iteritems():
        netconfig.add_interface_config(key, entry)

    return netconfig

def netmachineconfig_to_xml(machine_data):
    info = machine_data["info"]

    hostname = ""
    rootpass = ""
    rpcport = ""

    if "hostname" in info:
        hostname = "hostname=\"%s\" " % info["hostname"]
    if "rootpass" in info:
        rootpass = "rootpass=\"%s\" " % info["rootpass"]
    if "rpcport" in info:
        rpcport = "rpcport=\"%s\" " % info["rpcport"]

    info_tag = "    <info %s%s%s/>\n" % (hostname, rootpass, rpcport)

    devices = ""
    for phys_id, netdev in machine_data["netdevices"].iteritems():
        pid = "phys_id=\"%s\" " % phys_id
        dev_type = ""
        name = ""
        hwaddr = ""

        if "type" in netdev:
            dev_type = "type=\"%s\" " % netdev["type"]
        if "name" in netdev:
            name = "name=\"%s\" " % netdev["name"]
        if "hwaddr" in netdev:
            hwaddr = "hwaddr=\"%s\" " % netdev["hwaddr"]

        device_tag = "    <netdevice %s%s%s%s/>\n" % (pid, dev_type,
                                                      name, hwaddr)
        devices += device_tag

    return "<netmachineconfig>\n" + info_tag + devices + "</netmachineconfig>"

def main():
    """
    Main function
    """

    try:
        opts, args = getopt.getopt(
            sys.argv[1:],
            "dhc:m:a:",
            ["debug", "help", "config=", "machine-config=", "action="]
        )
    except getopt.GetoptError as err:
        print str(err)
        usage()
        sys.exit()

    debug = False
    config_path = None
    machine_config_path = None
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
        elif opt in ("-h", "--help"):
            usage()
        elif opt in ("-c", "--config"):
            config_path = arg
        elif opt in ("-m", "--machine-config"):
            machine_config_path = arg

    Logs(debug)
    logging.info("Started")

    if not args:
        logging.error("No action command passed")
        usage();

    action = args[0]
    if action == "cleanup":
        NetConfigDeviceAllCleanup()
        return

    if not machine_config_path:
        logging.error("No machine config xml file passed")
        usage();
    machine_config_path = os.path.expanduser(machine_config_path)

    if action == "refresh":
        logging.info("Refreshing machine config")
        machine_data = prepare_machine_config(machine_config_path)
        dev_names = NetConfigDevNames()
        for dev_id, netdev in machine_data["netdevices"].iteritems():
            if "name" in netdev:
                del netdev["name"]
            dev_names.assign_name_by_scan(dev_id, netdev)

        output = netmachineconfig_to_xml(machine_data)
        handle = open(machine_config_path, "w")
        handle.write(output)
        handle.close()
        return

    if not config_path:
        logging.error("No net config file/dir passed")
        usage();
    config_path = os.path.expanduser(config_path)

    if action == "test":
        '''
        Go through specified directory and use all xmls and configs
        '''

        for root, dirs, files in os.walk(config_path):
            for file_name in files:
                config_file = os.path.join(config_path, file_name)
                if not re.match(r'^.*\.xml$', config_file):
                    continue
                logging.info("Processing config file \"%s\"", config_file)
                net_config = prepare_netconfig(machine_config_path,
                                               config_file)
                net_config.configure_all()
                net_config.deconfigure_all()
        return

    net_config = prepare_netconfig(machine_config_path, config_path)
    if action == "up":
        net_config.configure_all()
    elif action == "down":
        net_config.deconfigure_all()
    elif action == "dump":
        pprint(net_config.dump_config())
    else:
        logging.error("unknown action \"%s\"" % action)

if __name__ == "__main__":
    main()
