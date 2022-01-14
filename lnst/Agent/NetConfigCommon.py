"""
This module defines common stuff for NetConfig

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jpirko@redhat.com (Jiri Pirko)
"""

def get_slaves(netdev):
    try:
        return netdev["slaves"]
    except KeyError:
        return set()

def get_option(netdev, opt_name):
    try:
        options = netdev["options"]
    except KeyError:
        return None
    for option, value in options:
        if option == opt_name:
            return value
    return None

def get_slave_option(netdev, slave_id, opt_name):
    try:
        options = netdev["slave_options"][slave_id]
    except KeyError:
        return None
    for option, value in options:
        if option == opt_name:
            return value
    return None

def get_slave_options(netdev, slave_id):
    try:
        options = netdev["slave_options"][slave_id]
    except KeyError:
        return []
    return options

def get_netem_option(netem_tag, netem_name, opt_name):
    try:
        options = netem_tag[netem_name]
    except KeyError:
        return None
    for opt in options:
        if opt["name"] == opt_name:
            return opt["value"]

def parse_delay(config):
    time = get_netem_option(config, "delay", "time")
    jitter= get_netem_option(config, "delay", "jitter")
    correlation = get_netem_option(config, "delay", "correlation")
    distribution = get_netem_option(config, "delay", "distribution")
    rv = "delay %s " % time
    if jitter is not None:
        rv = rv + "%s " % jitter
        if correlation is not None:
            rv = rv + "%s " % correlation
        if distribution is not None:
                rv = rv + "distribution %s " % distribution
    return rv

def parse_loss(config):
    percent = get_netem_option(config, "loss", "percent")
    correlation = get_netem_option(config, "loss", "correlation")
    rv = "loss %s " % percent
    if correlation is not None:
        rv = rv + "%s " % correlation
    return rv

def parse_corrupt(config):
    percent = get_netem_option(config, "corrupt", "percent")
    correlation = get_netem_option(config, "corrupt", "correlation")
    rv = "corrupt %s " % percent
    if correlation is not None:
        rv = rv + "%s " % correlation
    return rv

def parse_duplication(config):
    percent = get_netem_option(config, "duplication", "percent")
    correlation = get_netem_option(config, "duplication", "correlation")
    rv = "duplicate %s " % percent
    if correlation is not None:
        rv = rv + "%s " % correlation
    return rv

def parse_reordering(config):
    percent = get_netem_option(config, "reordering", "percent")
    correlation = get_netem_option(config, "reordering", "correlation")
    gap_distance = get_netem_option(config, "reordering", "gap_distance")
    rv = "reorder %s " % percent
    if correlation is not None:
        rv = rv + "%s " % correlation
    if gap_distance is not None:
        rv = rv + "gap %s " % gap_distance
    return rv

def parse_netem(config):
    rv = ""
    # delay parsing
    if "delay" in config:
        rv = rv + parse_delay(config)
    # loss parsing
    if "loss" in config:
        rv = rv + parse_loss(config)
    # corrupt
    if "corrupt" in config:
        rv = rv + parse_corrupt(config)
    # duplication
    if "duplication" in config:
        rv = rv + parse_duplication(config)
    # reordering
    if "reordering" in config:
        rv = rv + parse_reordering(config)
    return rv
