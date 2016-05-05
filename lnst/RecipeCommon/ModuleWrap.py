"""
This module defines helper functions for using test modules from Python Tasks

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

from lnst.Controller.Task import ctl

def ping(src, dst, options={}, expect="pass"):
    """ Perform an IcmpPing from source to destination

    Keyword arguments:
    src -- tuple of (HostAPI, InterfaceAPI/DeviceAPI, ip address index, ip addr selector)
    dst -- tuple of (HostAPI, InterfaceAPI/DeviceAPI, ip address index, ip addr selector)
    options -- dictionary of options for the IcmpPing module, can't contain
        keys 'addr' and 'iface'
    """

    options = dict(options)
    if 'addr' in options or 'iface' in options:
        raise Exception("options can't contain keys 'addr' and 'iface'")

    if not isinstance(src, tuple) or len(src) < 2 or len(src) > 4:
        raise Exception('Invalid source specification')
    try:
        if len(src) == 2:
            h1, if1 = src
            options["iface"] = if1.get_devname()
        elif len(src) == 3:
            h1, if1, addr_index1 = src
            options["iface"] = if1.get_ip(addr_index1)
        elif len(src) == 4:
            h1, if1, addr_index1, addr_selector1 = src
            options["iface"] = if1.get_ip(addr_index1, selector=addr_selector1)
    except:
        raise Exception('Invalid source specification')

    if not isinstance(dst, tuple) or len(dst) < 3 or len(dst) > 4:
        raise Exception('Invalid destination specification')
    try:
        if len(dst) == 3:
            h2, if2, addr_index2 = dst
            options["addr"] = if2.get_ip(addr_index2)
        elif len(dst) == 4:
            h2, if2, addr_index2, addr_selector2 = dst
            options["addr"] = if2.get_ip(addr_index2, selector=addr_selector2)
    except:
        raise Exception('Invalid destination specification')

    ping_mod = ctl.get_module("IcmpPing",
                              options = options)

    return h1.run(ping_mod, expect=expect)

def ping6(src, dst, options={}, expect="pass"):
    """ Perform an Icmp6Ping from source to destination

    Keyword arguments:
    src -- tuple of (HostAPI, InterfaceAPI/DeviceAPI, ip address index, ip addr selector)
    dst -- tuple of (HostAPI, InterfaceAPI/DeviceAPI, ip address index, ip addr selector)
    options -- dictionary of options for the IcmpPing module, can't contain
        keys 'addr' and 'iface'
    """

    options = dict(options)
    if 'addr' in options or 'iface' in options:
        raise Exception("options can't contain keys 'addr' and 'iface'")

    if not isinstance(src, tuple) or len(src) < 2 or len(src) > 4:
        raise Exception('Invalid source specification')
    try:
        if len(src) == 2:
            h1, if1 = src
            options["iface"] = if1.get_devname()
        elif len(src) == 3:
            h1, if1, addr_index1 = src
            options["iface"] = if1.get_ip(addr_index1)
        elif len(src) == 4:
            h1, if1, addr_index1, addr_selector1 = src
            options["iface"] = if1.get_ip(addr_index1, selector=addr_selector1)
    except:
        raise Exception('Invalid source specification')

    if not isinstance(dst, tuple) or len(dst) < 3 or len(dst) > 4:
        raise Exception('Invalid destination specification')
    try:
        if len(dst) == 3:
            h2, if2, addr_index2 = dst
            options["addr"] = if2.get_ip(addr_index2)
        elif len(dst) == 4:
            h2, if2, addr_index2, addr_selector2 = dst
            options["addr"] = if2.get_ip(addr_index2, selector=addr_selector2)
    except:
        raise Exception('Invalid destination specification')

    ping_mod = ctl.get_module("Icmp6Ping",
                              options = options)

    return h1.run(ping_mod, expect=expect)

def netperf(src, dst, server_opts={}, client_opts={}, baseline={}, timeout=60):
    """ Start a Netserver on the given machine and ip address

    Keyword arguments:
    src -- tuple of (HostAPI, InterfaceAPI/DeviceAPI, ip address index, ip addr selector)
    dst -- tuple of (HostAPI, InterfaceAPI/DeviceAPI, ip address index, ip addr selector)
    server_opts -- dictionary of additional options for the netperf server
        can't contain 'bind' or 'role'
    client_opts -- dictionary of additional options for the netperf client
        can't contain 'bind', 'role', 'netperf_server', 'threshold'
        or 'threshold_deviation'
    baseline -- optional dictionary with keys 'threshold' and 'threshold_deviation'
        that specifies the baseline of the netperf test
    timeout -- integer number of seconds specifing the maximum amount of time
        for the test, defaults to 60
    """

    server_opts = dict(server_opts)
    if 'bind' in server_opts or 'role' in server_opts:
        raise Exception("server_opts can't contain keys 'bind' and 'role'")

    client_opts = dict(client_opts)
    if 'bind' in client_opts or\
       'role' in client_opts or\
       'netperf_server' in client_opts:
        raise Exception("client_opts can't contain keys 'bind', 'role' "\
                        "and 'netperf_server'")

    if not isinstance(src, tuple) or len(src) < 2 or len(src) > 4:
        raise Exception('Invalid source specification')
    try:
        if len(src) == 3:
            h1, if1, addr_index1 = src
            client_ip = if1.get_ip(addr_index1)
        elif len(src) == 4:
            h1, if1, addr_index1, addr_selector1 = src
            client_ip = if1.get_ip(addr_index1, selector=addr_selector1)
    except:
        raise Exception('Invalid source specification')

    if not isinstance(dst, tuple) or len(dst) < 3 or len(dst) > 4:
        raise Exception('Invalid destination specification')
    try:
        if len(dst) == 3:
            h2, if2, addr_index2 = dst
            server_ip = if2.get_ip(addr_index2)
        elif len(dst) == 4:
            h2, if2, addr_index2, addr_selector2 = dst
            server_ip = if2.get_ip(addr_index2, addr_selector2)
    except:
        raise Exception('Invalid destination specification')

    server_opts["role"] = "server"
    server_opts["bind"] = server_ip

    client_opts["role"] = "client"
    client_opts["bind"] = client_ip
    client_opts["netperf_server"] = server_ip

    if "threshold" in baseline:
        client_opts["threshold"] = baseline["threshold"]
    if "threshold_deviation" in baseline:
        client_opts["threshold_deviation"] = baseline["threshold_deviation"]

    netserver_mod = ctl.get_module("Netperf", options=server_opts)
    netclient_mod = ctl.get_module("Netperf", options=client_opts)

    netserver = h2.run(netserver_mod, bg=True)
    ctl.wait(2)
    result = h1.run(netclient_mod, timeout=timeout)

    netserver.intr()
    return result
