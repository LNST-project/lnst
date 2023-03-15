"""
Various common functions

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import functools
import logging
import time
import re
import os
import psutil
import hashlib
import tempfile
import subprocess
import errno
import ast
import collections
import math
import itertools
from collections.abc import Iterable
from contextlib import AbstractContextManager
from _ast import Call, Attribute
from lnst.Common.ExecCmd import exec_cmd

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

def kmod_in_use(modulename, tries = 1):
    tries -= 1
    ret = False
    mod_file = "/proc/modules"
    handle = open(mod_file, "r")
    for line in handle:
        match = re.match(r'^(\S+)\s\d+\s(\d+).*$', line)
        if not match or not match.groups()[0] in re.split('\s+', modulename):
            continue
        if int(match.groups()[1]) != 0:
            ret = True
        break
    handle.close()
    if (ret and tries):
        return kmod_in_use(modulename, tries)
    return ret

def int_it(val):
    try:
        num = int(val)
    except ValueError:
        num = 0
    return num

def bool_it(val):
    if isinstance(val, str):
        if re.match("^\s*(true|yes)", val, flags=re.IGNORECASE):
            return True
        elif re.match("^\s*(false|no)", val, flags=re.IGNORECASE):
            return False
    return True if int_it(val) else False

def md5sum(file_path, block_size=2**20):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(block_size)
            if not data:
                break
            md5.update(data)

    return md5.hexdigest()

def sha256sum(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break
            sha256.update(data)

    return sha256.hexdigest()

def create_tar_archive(input_path, target_path, compression=False):
    if compression:
        args = "cfj"
    else:
        args = "cf"

    input_path = input_path.rstrip("/")
    input_file = os.path.basename(input_path)
    parent = os.path.dirname(input_path)

    if os.path.isdir(target_path):
        target_path += "/%s.tar.bz" % os.path.basename(input_file.rstrip("/"))

    exec_cmd("cd \"%s\" && tar %s \"%s\" \"%s\"" % \
                (parent, args, target_path, input_file))

    return target_path

def dir_md5sum(dir_path):
    tmp_file = tempfile.NamedTemporaryFile(delete=False)
    tmp_file.close()

    tar_filepath = create_tar_archive(dir_path, tmp_file.name)
    md5_digest = md5sum(tar_filepath)

    os.unlink(tar_filepath)

    return md5_digest

def has_changed_since(filepath, threshold):
    if os.path.isfile(filepath):
        return _is_newer_than(filepath, threshold)

    for root, dirs, files in os.walk(filepath):
        for f in files:
            if _is_newer_than(f, threshold):
                return False

        for d in dirs:
            if _is_newer_than(d, threshold):
                return False

    return True

def _is_newer_than(f, threshold):
    stat = os.stat(f)
    return stat.st_mtime > threshold

def check_process_running(process_name):
    return process_name in (p.info["name"] for p in psutil.process_iter(["name"]))

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def get_module_tools(module_path):
    tools = []

    f = open(module_path)

    asttree = ast.parse(f.read())

    for node in ast.walk(asttree):
        if isinstance (node, Call):
            fn = getattr(node, 'func')
            if isinstance(fn, Attribute):
                val = getattr(fn, 'value')
                if not isinstance(val, ast.Name):
                    continue
                if ('self' == getattr(val, 'id')):
                    if ( 'exec_from' == getattr(fn, 'attr')):
                        tool = getattr((getattr(node, 'args')[0]), 's')
                        tools.append(tool)

    f.close()

    return tools

def recursive_dict_update(original, update):
    for key, value in list(update.items()):
        if isinstance(value, collections.Mapping):
            r = recursive_dict_update(original.get(key, {}), value)
            original[key] = r
        else:
            original[key] = update[key]
    return original

def dot_to_dict(name, value):
    result = {}
    last = result
    last_key = None
    previous = None
    for key in name.split('.'):
        last[key] = {}
        previous = last
        last = last[key]
        last_key = key
    if last_key != None:
        previous[last_key] = value
    return result

def list_to_dot(original_list, prefix="", key=""):
    return_list = []
    index = 0
    for value in original_list:
        iter_key = prefix + key + str(index)
        index += 1
        if isinstance(value, collections.Mapping):
            sub_list = dict_to_dot(value, iter_key + '.')
            return_list.extend(sub_list)
        elif isinstance(value, list):
            raise Exception("Nested lists not allowed")
        elif isinstance(value, tuple):
            #TODO temporary fix, tuples shouldn't be here
            if len(value) == 2:
                return_list.append((iter_key+'.'+value[0], value[1]))
        else:
            return_list.append((iter_key, value))
    return return_list

def dict_to_dot(original_dict, prefix=""):
    return_list = []
    for key, value in list(original_dict.items()):
        if isinstance(value, collections.Mapping):
            sub_list = dict_to_dot(value, prefix + key + '.')
            return_list.extend(sub_list)
        elif isinstance(value, list):
            sub_list = list_to_dot(value, prefix, key)
            return_list.extend(sub_list)
        elif isinstance(value, tuple):
            #TODO temporary fix, tuples shouldn't be here
            if len(value) == 2:
                return_list.append((prefix+key,
                                    "(%s, %s)" % (value[0],
                                                  value[1]) ))
        else:
            return_list.append((prefix+key, str(value)))
    return return_list

def std_deviation(values):
    if len(values) <= 0:
        return 0.0
    avg = sum(values) / float(len(values))
    return math.sqrt(sum([(float(i) - avg)**2 for i in values])/len(values))

def deprecated(func):
    """
    Decorator which marks the method as deprecated - meaning when used,
    it logs warning message with name of the method and class it belongs to
    """

    @functools.wraps(func)
    def log(self, *args, **kwargs):
        logging.warning("Function %s from class %s is deprecated, please, "\
                        "check documentation for up-to-date method"
                        % (func.__name__, self.__class__.__name__))
        return func(self, *args, **kwargs)
    return log

def is_installed(program):
    """
    Returns True if program is detected by which, False otherwise
    """
    cmd = f"command -v {program}"
    try:
        subprocess.check_call(cmd, shell=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def indent(string, spaces):
    ret_str = []
    for line in string.split('\n'):
        if line == "":
            ret_str.append(line)
        else:
            ret_str.append(' '*spaces + line)
    return '\n'.join(ret_str)

class Noop(object):
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            pass
        return noop

def not_imported(*args, **kwargs):
    raise Exception("Object not imported.")


def pairwise(iterable: Iterable) -> Iterable:
    """
    s -> (s0,s1), (s1,s2), (s2, s3), ...
    https://docs.python.org/3/library/itertools.html#itertools-recipes
    """
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


class nullcontext(AbstractContextManager):
    """
    Context manager that does no additional processing.
    Used as a stand-in for a normal context manager, when a particular
    block of code is only sometimes used with a normal context manager:
    cm = optional_cm if condition else nullcontext()
    with cm:
        # Perform operation, using optional_cm if condition is True

    Copied from
        https://github.com/python/cpython/blob/3.9/Lib/contextlib.py
    To backport it for python 3.6 (it was added in 3.7).
    """

    def __init__(self, enter_result=None):
        self.enter_result = enter_result

    def __enter__(self):
        return self.enter_result

    def __exit__(self, *excinfo):
        pass
