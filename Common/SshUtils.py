"""
Ssh utils.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""

import time, logging
from ShellProcess import ShellProcess

class LoginError(Exception):
    def __init__(self, msg, output):
        Exception.__init__(self, msg, output)
        self.msg = msg
        self.output = output

    def __str__(self):
        return "%s    (output: %r)" % (self.msg, self.output)


class LoginAuthenticationError(LoginError):
    pass


class LoginTimeoutError(LoginError):
    def __init__(self, output):
        LoginError.__init__(self, "Login timeout expired", output)


class LoginProcessTerminatedError(LoginError):
    def __init__(self, status, output):
        LoginError.__init__(self, None, output)
        self.status = status

    def __str__(self):
        return ("Client process terminated    (status: %s,    output: %r)" %
                (self.status, self.output))


class LoginBadClientError(LoginError):
    def __init__(self, client):
        LoginError.__init__(self, None, None)
        self.client = client

    def __str__(self):
        return "Unknown remote shell client: %r" % self.client


class SCPError(Exception):
    def __init__(self, msg, output):
        Exception.__init__(self, msg, output)
        self.msg = msg
        self.output = output

    def __str__(self):
        return "%s    (output: %r)" % (self.msg, self.output)


class SCPAuthenticationError(SCPError):
    pass


class SCPAuthenticationTimeoutError(SCPAuthenticationError):
    def __init__(self, output):
        SCPAuthenticationError.__init__(self, "Authentication timeout expired",
                                        output)


class SCPTransferTimeoutError(SCPError):
    def __init__(self, output):
        SCPError.__init__(self, "Transfer timeout expired", output)


class SCPTransferFailedError(SCPError):
    def __init__(self, status, output):
        SCPError.__init__(self, None, output)
        self.status = status

    def __str__(self):
        return ("SCP transfer failed    (status: %s,    output: %r)" %
                (self.status, self.output))


def _remote_login(session, username, password, prompt, timeout=10):
    """
    Log into a remote host (guest) using SSH or Telnet.  Wait for questions
    and provide answers.  If timeout expires while waiting for output from the
    child (e.g. a password prompt or a shell prompt) -- fail.

    @brief: Log into a remote host (guest) using SSH or Telnet.

    @param session: An Expect or ShellSession instance to operate on
    @param username: The username to send in reply to a login prompt
    @param password: The password to send in reply to a password prompt
    @param prompt: The shell prompt that indicates a successful login
    @param timeout: The maximal time duration (in seconds) to wait for each
            step of the login procedure (i.e. the "Are you sure" prompt, the
            password prompt, the shell prompt, etc)
    @raise LoginTimeoutError: If timeout expires
    @raise LoginAuthenticationError: If authentication fails
    @raise LoginProcessTerminatedError: If the client terminates during login
    @raise LoginError: If some other error occurs
    """
    password_prompt_count = 0
    login_prompt_count = 0

    while True:
        try:
            match, text = session.read_until_output_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"[Ll]ogin:\s*$",
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused",
                 r"[Pp]lease wait", prompt],
                timeout=timeout, internal_timeout=2)
            if match == 0:  # "Are you sure you want to continue connecting"
                logging.log(logging.DEBUG2, "Got 'Are you sure...'; sending 'yes'")
                session.sendline("yes")
                continue
            elif match == 1:  # "password:"
                if password_prompt_count == 0:
                    logging.log(logging.DEBUG2, "Got password prompt; sending '%s'", password)
                    session.sendline(password)
                    password_prompt_count += 1
                    continue
                else:
                    raise LoginAuthenticationError("Got password prompt twice",
                                                   text)
            elif match == 2:  # "login:"
                if login_prompt_count == 0 and password_prompt_count == 0:
                    logging.log(logging.DEBUG2, "Got username prompt; sending '%s'", username)
                    session.sendline(username)
                    login_prompt_count += 1
                    continue
                else:
                    if login_prompt_count > 0:
                        msg = "Got username prompt twice"
                    else:
                        msg = "Got username prompt after password prompt"
                    raise LoginAuthenticationError(msg, text)
            elif match == 3:  # "Connection closed"
                logging.log(logging.INFO, "Remote command execution successful")
                break
            elif match == 4:  # "Connection refused"
                raise LoginError("Client said 'connection refused'", text)
            elif match == 5:  # "Please wait"
                logging.log(logging.DEBUG2, "Got 'Please wait'")
                timeout = 30
                continue
            elif match == 6:  # prompt
                logging.log(logging.INFO, "Got shell prompt -- logged in")
                break
        except ShellProcess.ProcessTimeoutError, e:
            raise LoginTimeoutError(e.output)
        except ShellProcess.ProcessTerminatedError, e:
            raise LoginProcessTerminatedError(e.status, e.output)


def remote_login(host, port, username, password, prompt, linesep="\n",
                 log_filename=None, timeout=10, command=None):
    """
    Log into a remote host (guest) using SSH/Telnet/Netcat.

    @param client: The client to use ('ssh', 'telnet' or 'nc')
    @param host: Hostname or IP address
    @param port: Port to connect to
    @param username: Username (if required)
    @param password: Password (if required)
    @param prompt: Shell prompt (regular expression)
    @param linesep: The line separator to use when sending lines
            (e.g. '\\n' or '\\r\\n')
    @param log_filename: If specified, log all output to this file
    @param timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt
            or the password prompt)
    @raise LoginBadClientError: If an unknown client is requested
    @raise: Whatever _remote_login() raises
    @return: A ShellSession object.
    """
    if command is None:
        command = ""
    else:
        command = "-C '%s'" % (command)
    cmd = ("ssh -t -o ServerAliveInterval=5 -o ServerAliveCountMax=2 -o UserKnownHostsFile=/dev/null "
           "-p %s %s@%s %s" % #-o PreferredAuthentications=password
           (port, username, host, command))

    logging.log(logging.DEBUG2, "Trying to login with command '%s'", cmd)
    session = ShellProcess(cmd, linesep=linesep, debug_level=logging.DEBUG2,
                           process_manager=True)
    try:
        _remote_login(session, username, password, prompt, timeout)
    except:
        raise
    if log_filename:
        pass
        #session.set_output_params((log_filename,))
    return session


def wait_for_login(host, port, username, password, prompt, linesep="\n",
                   log_filename=None, timeout=240, internal_timeout=10,
                   command = ""):
    """
    Make multiple attempts to log into a remote host (guest) until one succeeds
    or timeout expires.

    @param timeout: Total time duration to wait for a successful login
    @param internal_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (e.g. the "Are you sure" prompt
            or the password prompt)
    @see: remote_login()
    @raise: Whatever remote_login() raises
    @return: A ShellSession object.
    """
    logging.debug("Attempting to log into %s:%s (timeout %ds)",
                  host, port,  timeout)
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            return remote_login(host, port, username, password, prompt,
                                linesep, log_filename, internal_timeout,
                                command)
        except LoginError, e:
            logging.debug(e)
        time.sleep(2)
    # Timeout expired; try one more time but don't catch exceptions
    return remote_login(host, port, username, password, prompt,
                        linesep, log_filename, internal_timeout, command)


def _remote_scp(session, password_list, transfer_timeout=600, login_timeout=10):
    """
    Transfer file(s) to a remote host (guest) using SCP.  Wait for questions
    and provide answers.  If login_timeout expires while waiting for output
    from the child (e.g. a password prompt), fail.  If transfer_timeout expires
    while waiting for the transfer to complete, fail.

    @brief: Transfer files using SCP, given a command line.

    @param session: An Expect or ShellSession instance to operate on
    @param password_list: Password list to send in reply to the password prompt
    @param transfer_timeout: The time duration (in seconds) to wait for the
            transfer to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt or
            the password prompt)
    @raise SCPAuthenticationError: If authentication fails
    @raise SCPTransferTimeoutError: If the transfer fails to complete in time
    @raise SCPTransferFailedError: If the process terminates with a nonzero
            exit code
    @raise SCPError: If some other error occurs
    """
    password_prompt_count = 0
    timeout = login_timeout
    authentication_done = False

    scp_type = len(password_list)

    while True:
        try:
            match, text = session.read_until_output_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*$", r"lost connection",
                 r"Exit status 0"],
                timeout=timeout, internal_timeout=5)
            if match == 0:  # "Are you sure you want to continue connecting"
                logging.log(logging.DEBUG2, "Got 'Are you sure...'; sending 'yes'")
                session.sendline("yes")
                continue
            elif match == 1:  # "password:"
                if password_prompt_count == 0:
                    logging.log(logging.DEBUG2, "Got password prompt; sending '%s'" %
                                   password_list[password_prompt_count])
                    try:
                        session.sendline(password_list[password_prompt_count])
                    except TypeError:
                        logging.error("For logging is necessary set rootpass"+
                                      " in config.")
                        raise
                    password_prompt_count += 1
                    timeout = transfer_timeout
                    if scp_type == 1:
                        authentication_done = True
                    continue
                elif password_prompt_count == 1 and scp_type == 2:
                    logging.log(logging.DEBUG2, "Got password prompt; sending '%s'" %
                                   password_list[password_prompt_count])
                    session.sendline(password_list[password_prompt_count])
                    password_prompt_count += 1
                    timeout = transfer_timeout
                    authentication_done = True
                    continue
                else:
                    raise SCPAuthenticationError("Got password prompt twice",
                                                 text)
            elif match == 2:  # "lost connection"
                raise SCPError("SCP client said 'lost connection'", text)
            """elif match == 3: #Exit transfer correctly.
                logging.log(logging.DEBUG2, "SCP process terminated with status 0")
                break"""
        except ShellProcess.ProcessTimeoutError, e:
            if authentication_done:
                raise SCPTransferTimeoutError(e.output)
            else:
                raise SCPAuthenticationTimeoutError(e.output)
        except ShellProcess.ProcessTerminatedError, e:
            if e.status == 0:
                logging.log(logging.DEBUG2, "SCP process terminated with status 0")
                break
            else:
                raise SCPTransferFailedError(e.status, e.output)


def remote_scp(command, password_list, log_filename=None, transfer_timeout=600,
               login_timeout=10):
    """
    Transfer file(s) to a remote host (guest) using SCP.

    @brief: Transfer files using SCP, given a command line.

    @param command: The command to execute
        (e.g. "scp -r foobar root@localhost:/tmp/").
    @param password_list: Password list to send in reply to a password prompt.
    @param log_filename: If specified, log all output to this file
    @param transfer_timeout: The time duration (in seconds) to wait for the
            transfer to complete.
    @param login_timeout: The maximal time duration (in seconds) to wait for
            each step of the login procedure (i.e. the "Are you sure" prompt
            or the password prompt)
    @raise: Whatever _remote_scp() raises
    """
    logging.debug("Trying to SCP with command '%s', timeout %ss",
                  command, transfer_timeout)
    if log_filename:
        pass
        #output_func = log_line
        #output_params = (log_filename,)
    else:
        pass
        #output_func = None
        #output_params = ()
    session = ShellProcess(command, debug_level=logging.DEBUG2)
    _remote_scp(session, password_list, transfer_timeout, login_timeout)


def scp_to_remote(host, port, username, password, local_path, remote_path,
                  log_filename=None, timeout=600):
    """
    Copy files to a remote host (guest) through scp.

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param log_filename: If specified, log all output to this file
    @param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    @raise: Whatever remote_scp() raises
    """
    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               " -r -P %s '%s' '%s@%s:%s'" % #-o PreferredAuthentications=password
               (port, local_path, username, host, remote_path))
    password_list = []
    password_list.append(password)
    remote_scp(command, password_list, log_filename, timeout)
    logging.info("Copy to remote machine (%s) pass." % host)


def scp_from_remote(host, port, username, password, remote_path, local_path,
                    log_filename=None, timeout=600):
    """
    Copy files from a remote host (guest).

    @param host: Hostname or IP address
    @param username: Username (if required)
    @param password: Password (if required)
    @param local_path: Path on the local machine where we are copying from
    @param remote_path: Path on the remote machine where we are copying to
    @param log_filename: If specified, log all output to this file
    @param timeout: The time duration (in seconds) to wait for the transfer
            to complete.
    @raise: Whatever remote_scp() raises
    """
    command = ("scp -v -o UserKnownHostsFile=/dev/null "
               "-o PreferredAuthentications=password -r -P %s '%s@%s:%s' '%s'" %
               (port, username, host, remote_path, local_path))
    password_list = []
    password_list.append(password)
    remote_scp(command, password_list, log_filename, timeout)
    logging.info("Copy from remote machine (%s) pass." % host)


def scp_between_remotes(src, dst, port, s_passwd, d_passwd, s_name, d_name,
                        s_path, d_path, log_filename=None, timeout=600):
    """
    Copy files from a remote host (guest) to another remote host (guest).

    @param src/dst: Hostname or IP address of src and dst
    @param s_name/d_name: Username (if required)
    @param s_passwd/d_passwd: Password (if required)
    @param s_path/d_path: Path on the remote machine where we are copying
                         from/to
    @param log_filename: If specified, log all output to this file
    @param timeout: The time duration (in seconds) to wait for the transfer
            to complete.

    @return: True on success and False on failure.
    """
    command = ("scp -v -o UserKnownHostsFile=/dev/null -o "
               "PreferredAuthentications=password -r -P %s '%s@%s:%s' '%s@%s:%s'" %
               (port, s_name, src, s_path, d_name, dst, d_path))
    password_list = []
    password_list.append(s_passwd)
    password_list.append(d_passwd)
    remote_scp(command, password_list, log_filename, timeout)
    logging.info("Copy betwen remote machines (%s) and (%s) pass." % (src, dst))
