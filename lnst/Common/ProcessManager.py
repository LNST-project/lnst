"""
ShellProcess class.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import os, signal, _thread, logging

class ProcessManager:
    class SubProcess:
        def __init__(self, pid, handler):
            self.pid = pid
            self.lock = _thread.allocate_lock()
            self.lock.acquire()
            self.handler = handler
            self.enabled = True
            self.status = None
            _thread.start_new_thread(self.waitpid, (self.pid, self.lock,
                                                   self.handler))

        def isAlive(self):
            return self.lock.locked()

        def kill(self):
            os.kill(self.pid, signal.SIGTERM)

        def waitpid(self, pid, lock, handler):
            _pid, status = ProcessManager.std_waitpid(pid, 0)
            self.status = status
            status = os.WEXITSTATUS(status)
            lock.release()
            if self.enabled:
                ProcessManager.lock.acquire()
                if handler is not None:
                    try:
                        handler(status)
                    except:
                        import sys, traceback
                        type, value, tb = sys.exc_info()
                        logging.error(''.join(traceback.format_exception(type, value, tb)))
                        os.kill(os.getpid(), signal.SIGTERM)
                else:
                    print("Process pid %s exit with exitcode %s" % (pid, status))
                ProcessManager.lock.release()
            _thread.exit()

    pids = {}
    lock = _thread.allocate_lock()
    std_waitpid = None

    @classmethod
    def register_pid(cls, pid, handler=None):
        cls.pids[pid] = ProcessManager.SubProcess(pid, handler)

    @classmethod
    def remove_pid(cls, pid):
        if pid in cls.pids:
            cls.pids[pid].enabled = False

    @classmethod
    def kill_all(cls):
        for pid in cls.pids:
            cls.pids[pid].kill()

    @classmethod
    def waitpid(cls, pid, wait):
        if pid not in cls.pids:
            return ProcessManager.std_waitpid(pid, wait)
        if not wait:
            cls.pids[pid].lock.acquire()
            cls.pids[pid].lock.release()
            status = cls.pids[pid].status
            del cls.pids[pid]
            return pid, status
        else:
            status = cls.pids[pid].status
            if status is not None:
                del cls.pids[pid]
            else:
                pid = 0
            return pid, status


lock = _thread.allocate_lock()
lock.acquire()
if os.waitpid != ProcessManager.waitpid:
    ProcessManager.std_waitpid = os.waitpid
    os.waitpid = ProcessManager.waitpid
lock.release()
