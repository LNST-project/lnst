"""
Various common functions

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import logging, time, subprocess, re, socket

def die_when_parent_die():
    try:
        import ctypes
        from ctypes.util import find_library
    except:
        logging.error("Failed to load ctype library.")
        raise
    libc = ctypes.CDLL(find_library("c"))
    PR_SET_PDEATHSIG = 1; TERM = 15
    libc.prctl(PR_SET_PDEATHSIG, TERM)


def wait_for(func, timeout, first=0.0, step=1.0, text=None):
    """
    If func() evaluates to True before timeout expires, return the
    value of func(). Otherwise return None.

    @brief: Wait until func() evaluates to True.

    @param timeout: Timeout in seconds
    @param first: Time to sleep before first attempt
    @param steps: Time to sleep between attempts in seconds
    @param text: Text to print while waiting, for debug purposes
    """
    start_time = time.time()
    end_time = time.time() + timeout

    time.sleep(first)
    while time.time() < end_time:
        if text:
            logging.debug("%s (%f secs)", text, (time.time() - start_time))

        output = func()
        if output:
            return output

        time.sleep(step)

    logging.debug("Timeout elapsed")
    return None


def get_corespond_local_ip(query_ip):
    """
    Get ip address in local system which can communicate with quert_ip.

    @param query_ip: IP of client which want communicate with autotest machine.
    @return: IP address which can communicate with query_ip
    """
    query_ip = socket.gethostbyname(query_ip)
    ip = subprocess.Popen("ip route get %s" % (query_ip),
                          shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ip = ip.communicate()[0]
    ip = re.search(r"src ([0-9.]*)",ip)
    if ip is None:
        return ip
    return ip.group(1)
