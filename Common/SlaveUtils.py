"""
Utils for general purpose.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""

from Common.SshUtils import scp_to_remote, wait_for_login
from Common.ShellProcess import ShellProcess
import sys

def prepare_client_session(host, port, login, passwd=None, command=None,
                           prompt=None, install_path=None, test_dir=None):
    """
    Copy nettest to client start client part
    and create session with client part.
    @param command: Command which is started after login to guest, in root
                    path of installed test.
    @param prompt: Prompt in guest side which means that guest side stared
                   correctly.
    @param test_dir: Path in install_path where is installed testing framework.
    @param install_path: Path to create and install test_dir folder.
    """
    if install_path is None:
        install_path = "/tmp"
    if test_dir is None:
        test_dir = "lnst"

    s = ShellProcess("tar -cjf lnst.tar.bz2 --exclude *.pyc --exclude 'Logs/*' -C '%s' ./" % sys.path[0])
    s.wait()
    scp_to_remote(host, port, login, passwd,
                  "lnst.tar.bz2","/%s/" % (install_path))
    wait_for_login(host, port, login, passwd, "PASS:",
                   command = "mkdir -p /%(ip)s/%(td)s && tar -xvjf "
                   "/%(ip)s/lnst.tar.bz2 -C /%(ip)s/%(td)s && echo PASS:" %
                   {"td":test_dir, "ip":install_path} , timeout=60)

    if prompt is None:
        prompt = "Started"
    command = "cd /%s/%s/ && ./%s" % (install_path, test_dir, command)
    return wait_for_login(host, port, login, passwd, prompt,
                          command=command, timeout=10)
