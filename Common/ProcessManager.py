"""
ShellProcess class.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import os, signal

class ProcessManager:
    pids = {}
    signals = 0

    @classmethod
    def register_pid(cls, pid, handler=None):
        cls.pids[pid] = handler

    @classmethod
    def remove_pid(cls, pid):
        if pid in cls.pids:
            del (cls.pids[pid])

    @classmethod
    def check_pids(cls):
        finished = {}
        pid_tr = []

        for pid in cls.pids:
            _pid = 0
            status = None
            try:
                _pid, status = os.waitpid(pid, os.WNOHANG)
            except OSError, e:
                if e.errno != 10:
                    raise
                else:
                    finished[pid] = (None, cls.pids[pid])
                    pid_tr.append(pid)
            else:
                if pid == _pid:
                    finished[pid] = (os.WEXITSTATUS(status), cls.pids[pid])
                    pid_tr.append(pid)

        for pid in pid_tr:
            cls.remove_pid(pid)
        return finished

    @classmethod
    def handler(cls, signum, frame):
        if (signum == signal.SIGCHLD):
            cls.signals += 1
            if cls.signals == 1:
                while cls.signals > 0:
                    finished = ProcessManager.check_pids()
                    for pid in finished:
                        status, handler = finished[pid]
                        if handler is None:
                            print("Process %d finish with status %s." % (pid, status))
                        else:
                            handler(status)
                    if cls.signals > 1:
                        cls.signals = 1
                    else:
                        cls.signals = 0


signal.siginterrupt(signal.SIGCHLD, False)
signal.signal(signal.SIGCHLD, ProcessManager.handler)
