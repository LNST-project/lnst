"""
This module defines the functions for Offloads tuning that can be imported
directly into LNST Python tasks.

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
kjerabek@redhat.com (Kamil Jerabek)
"""

import re

def parse_offloads(offloads):
    """Parse offloads combination in string to tuple, containing list of
    summary of all used offloads, and list of all offloads settings.
    The function parse all used offloads, in each set all offloads are on,
    except the ones specified as off.

    Keyword arguments:
    offloads -- string of offloads combination separated with ';'
    Expected input: "tso on gso on tx off; tso off tx off ;rx off".
    """

    if offloads is None:
        return None

    is_valid = re.compile(r"^([a-z\-]+\s+(off|on)(\s*[;]\s*|\s*))+$")
    opts_split = re.compile(r".*?(?=;)|.+$")
    opts_offloads_split = re.compile(r"([a-z]+(?=\s+(off|on)))+")
    offloads_split = re.compile(r"([a-z\-]+)(?=\s+off|\s+on)")

    if re.match(is_valid, offloads) is None:
        raise Exception('Invalid offloads format')

    offload_set = ([], [])
    sequence = re.findall(offloads_split, offloads)
    [offload_set[0].append(i) for i in sequence if not offload_set[0].count(i)]

    opts_match = filter(None, re.findall(opts_split, offloads))

    for opts in opts_match:
        sett = []
        match = re.findall(opts_offloads_split, opts)

        for offload in offload_set[0]:
            if (offload, 'off') in match:
                sett.append((offload, 'off'))
            else:
                sett.append((offload, 'on'))

        offload_set[1].append(sett)

    return offload_set
