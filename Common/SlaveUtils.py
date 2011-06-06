"""
Utils for general purpose.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""

from Common.SshUtils import scp_to_remote, wait_for_login
from Common.ShellProcess import ShellProcess


def prepare_client_session(host, port, login, passwd=None, command=None,
                           prompt=None):
    """
    Copy nettest to client start client part
    and create session with client part.
    @param command: Command which is started after login to guest.
    @param prompt: Prompt in guest side which means that guest side stared correctly.
    """
    s = ShellProcess("tar -cvzf nettest.tar.gz --exclude *.pyc --exclude 'Logs/*' *")
    s.wait()
    scp_to_remote(host, port, login, passwd,
                        "nettest.tar.gz","/tmp/")
    wait_for_login(host, port, login, passwd, "PASS:",
                       command = "mkdir -p /tmp/nettest && tar -xvzf "
                       "/tmp/nettest.tar.gz -C /tmp/nettest/ && echo PASS:",
                       timeout=60)

    if prompt is None:
        prompt = "Started"
    return wait_for_login(host, port, login, passwd, prompt,
                          command=command, timeout=10)
