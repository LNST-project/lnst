"""
This module contains helper functions useful when writing recipes
that use PerfRepo.

Copyright 2015 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
olichtne@redhat.com (Ondrej Lichtner)
"""

import re

def parse_id_mapping(filename):
    line_re = re.compile(r"^(\w+)\s*=\s*(\w+)$")
    res_dict = {}
    try:
        with open(filename) as f:
            for line in f:
                match = line_re.match(line)
                if match is not None:
                    res_dict[match.group(1)] = match.group(2)
    except:
        return None
    return res_dict

def get_id(mapping, key):
    try:
        return mapping[key]
    except (KeyError, TypeError):
        return None
