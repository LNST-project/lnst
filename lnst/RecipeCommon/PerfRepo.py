"""
This module defines helper functions for interacting with PerfRepo
that can be imported directly into LNST Python tasks.

Copyright 2016 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jtluka@redhat.com (Jan Tluka)
"""

import os

def generate_perfrepo_comment(hosts=[], user_comment=None):
    """ Prepare the PerfRepo comment.

    By default it will include kernel versions used on the hosts and
    Beaker job url.

    Keyword arguments:
    hosts -- list of HostAPI objects
    user_comment -- additional user specified comment
    """

    comment = ""

    for host in hosts:
        host_cfg = host.get_configuration()
        comment += "Kernel (%s): %s<BR>" % \
                       (host_cfg['id'], host_cfg['kernel_release'])

    # if we're running in Beaker environment, include job url
    if 'BEAKER' in os.environ and 'JOBID' in os.environ:
        bkr_server = os.environ['BEAKER']
        bkr_jobid = os.environ['JOBID']
        bkr_job_url = bkr_server + bkr_jobid
        comment += "Beaker job: %s<BR>" % bkr_job_url

    if user_comment:
        comment += user_comment

    return comment
