"""
ShellProcess class.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import pty, os, termios, time, signal, re, select
import logging, atexit
from Common.Utils import wait_for
from Common.ProcessManager import ProcessManager

class ShellProcess:
    class ProcessError(Exception):
        def __init__(self, patterns, output):
            Exception.__init__(self, patterns, output)
            self.patterns = patterns
            self.output = output

        def _pattern_str(self):
            if len(self.patterns) == 1:
                return "pattern %r" % self.patterns[0]
            else:
                return "patterns %r" % self.patterns

        def __str__(self):
            return ("Unknown error occurred while looking for %s    (output: %r)" %
                    (self._pattern_str(), self.output))


    class ProcessTimeoutError(ProcessError):
        def __str__(self):
            return ("Timeout expired while looking for %s    (output: %r)" %
                    (self._pattern_str(), self.output))


    class ProcessTerminatedError(ProcessError):
        def __init__(self, patterns, status, output):
            ShellProcess.ProcessError.__init__(self, patterns, output)
            self.status = status


        def __str__(self):
            return ("Process terminated while looking for %s    "
                    "(status: %s,    output: %r)" % (self._pattern_str(),
                                                     self.status, self.output))


    def __init__(self, command, linesep="\n", debug_level=logging.DEBUG,
                 process_manager=False):
        self.logging_level = debug_level
        self.command = command
        self.fd = None
        self.pid = None
        self.linesep = linesep
        self.status = None
        self.kill_handler = []
        ShellProcess._collect_session(self)
        self.killing = False
        self._execute()
        if process_manager:
            ProcessManager.register_pid(self.pid , self._die_event)


    _sessions = []
    @classmethod
    def _collect_session(cls, instance):
        ShellProcess._sessions.append(instance)


    @classmethod
    def kill_all_session(cls):
        for session in ShellProcess._sessions:
            session.kill()


    @classmethod
    def _del_session(cls, instance):
        ShellProcess._sessions.remove(instance)


    def __del__(self):
        ShellProcess._del_session(self)
        self.kill()


    def __repr__(self):
        return "<ShellProcess %s>" % (self.command)


    __str__ = __repr__


    def _execute(self):
        (self.pid, self.fd) = pty.fork()
        if self.pid == 0:
            # Child process: run the command in a subshell
            os.execv("/bin/sh", ["/bin/sh", "-c", self.command])
        else:
            attr = termios.tcgetattr(self.fd)
            attr[0] &= ~termios.INLCR
            attr[0] &= ~termios.ICRNL
            attr[0] &= ~termios.IGNCR
            attr[1] &= ~termios.OPOST
            attr[3] &= ~termios.ECHO
            termios.tcsetattr(self.fd, termios.TCSANOW, attr)


    def _die_event(self, status):
        """
        Started when client die.
        """
        if not self.killing:
            for handler in self.kill_handler:
                handler(self, status)


    def add_kill_handler(self, handler):
        """
        Add handler.
        Handler format handler(session)

        @param handler: handler which is called.
        """
        self.kill_handler.append(handler)


    def kill(self):
        """
        Kill subprocess
        """
        try:
            ProcessManager.remove_pid(self.pid)
            if self.get_status() is None:
                os.kill(self.pid, signal.SIGKILL)
                logging.debug("Killing PID %d" % self.pid)
            else:
                logging.debug("Process PID %d return %d" % (self.pid,
                                                            self.get_status()))
        except OSError:
            logging.log(self.logging_level,
                        "Process %d is already killed." % (self.pid))


    def get_status(self, infinite=False):
        """
        Get exit process status.
        """
        if self.status is None:
            pid = 0
            status = 0
            if infinite:
                pid, status = os.waitpid(self.pid, 0)
            else:
                pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid == self.pid:
                self.status = os.WEXITSTATUS(status)
        return self.status


    def is_alive(self):
        """
        Return true when process running.
        """
        self.status = self.get_status()
        if self.status == None:
            return True
        return False


    def send(self, str=""):
        """
        Send a string to the child process.

        @param str: String to send to the child process.
        """
        try:
            os.write(self.fd, str)
        except:
            pass


    def sendline(self, str=""):
        """
        Send a string followed by a line separator to the child process.

        @param str: String to send to the child process.
        """
        self.send(str + self.linesep)


    def match_patterns(self, str, patterns):
        """
        Match str against a list of patterns.

        Return the index of the first pattern that matches a substring of str.
        None and empty strings in patterns are ignored.
        If no match is found, return None.

        @param patterns: List of strings (regular expression patterns).
        """
        for i in range(len(patterns)):
            if not patterns[i]:
                continue
            if re.search(patterns[i], str):
                return i


    def read_nonblocking(self, timeout=None):
        """
        Read from child until there is nothing to read for timeout seconds.

        @param timeout: Time (seconds) to wait before we give up reading from
                the child process, or None to use the default value.
        """
        if timeout is None:
            timeout = 0.1
        fd = self.fd
        data = ""
        p = select.poll()
        p.register(fd , select.POLLIN)
        while True:
            try:
                r = p.poll(timeout*1e3)
            except:
                return data
            if r and (r[0][1] & select.POLLIN):
                new_data = os.read(fd, 1024)
                logging.log(self.logging_level, "data:\n" + new_data.rstrip())
                if not new_data:
                    return data
                data += new_data
            else:
                return data


    def read_until_output_matches(self, patterns, internal_timeout=0.1,
                                  timeout=60):
        logging.log(self.logging_level, "Timeout: %d" % (timeout))
        fd = self.fd
        out = ""
        end_time = time.time() + timeout
        p = select.poll()
        p.register(fd, select.POLLIN)

        while True:
            try:
                polled = p.poll((end_time-time.time())*1e3)
            except (select.error, TypeError):
                break
            if not polled:
                raise ShellProcess.ProcessTimeoutError(patterns, out)
            if polled and polled[0][1] == select.POLLHUP:
                break
            # Read data from child
            data = self.read_nonblocking(internal_timeout)
            if not data:
                break
            # Print it if necessary
            # Look for patterns
            out += data
            match = self.match_patterns(out, patterns)
            if match is not None:
                return match, out

        # Check if the child has terminated
        if wait_for(lambda: not self.is_alive(), 5, 0, 0.5):
            raise ShellProcess.ProcessTerminatedError(patterns,
                                                      self.get_status(),
                                                      out)
        else:
            # This shouldn't happen
            raise ShellProcess.ProcessError(patterns, out)


    def wait(self, timeout=None, step=0.2):
        """
        Wait for exit of subprocess.

        @param timeout:
        @return: Exit code.
        """
        if timeout is None:
            return self.get_status(True)
        else:
            wait_for(lambda: not self.is_alive(), timeout, 0, step)
        return self.get_status()

    def wait_for_command(self, command, prompts, timeout):
        """
        Wait for prompt of started command.

        @param prompts: Array of prompts
        """
        self.sendline(command)
        match, out = self.read_until_output_matches(prompts, 60)
        if match == None:
            raise ShellProcess.ProcessError(prompts, out)
        return (True, out)


atexit.register(ShellProcess.kill_all_session)
