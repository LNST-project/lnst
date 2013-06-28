"""
Utils for logging.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__autor__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import os, sys, shutil, datetime
from logging import Formatter
import logging.handlers
import traceback
from lnst.Common.LoggingHandler import LogBuffer
from lnst.Common.LoggingHandler import TransmitHandler
from lnst.Common.Colours import decorate_with_preset, strip_colours

def log_exc_traceback():
    cmd_type, value, tb = sys.exc_info()
    exception = traceback.format_exception(cmd_type, value, tb)
    logging.debug(''.join(exception))

class MultilineFormatter(Formatter): # addr:17 level:7
    _ADDR_WIDTH  = 17
    _LEVEL_WIDTH = 7
    _coloured    = False

    def __init__(self, coloured=False):
        fmt = "%(asctime)s  %(address)s  %(levelname)s: %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        self.linefmt = "    "
        self._coloured = coloured

        Formatter.__init__(self, fmt, datefmt)

    def _decorate_value(self, string, preset):
        value = strip_colours(string)
        if sys.stdout.isatty() and self._coloured:
            return decorate_with_preset(value, preset)
        else:
            return value

    def _format_addr(self, record):
        if not "address" in record.__dict__:
            addr = "(127.0.0.1)".rjust(17)
        else:
            addr = record.address.rjust(17)

        just  = " " * (self._ADDR_WIDTH - len(addr))
        return just + self._decorate_value(addr, "log_header")

    def _format_level(self, record):
        level = record.levelname

        just  = " " * (self._LEVEL_WIDTH - len(level))
        return just + self._decorate_value(level, level.lower())

    def format(self, record):
        values = {}

        asctime = self.formatTime(record, self.datefmt)
        values["asctime"] = self._decorate_value(asctime, "log_header")

        values["address"] = self._format_addr(record)
        values["levelname"] = self._format_level(record)

        msg = ""
        level = record.levelname
        lines = record.getMessage().split("\n")
        if len(lines) > 1:
            for line in lines:
                if level == "DEBUG":
                    line = self._decorate_value(line, "faded")
                msg += "\n" + self.linefmt + line
            values["message"] = msg
        else:
            if level == "DEBUG":
                values["message"] = self._decorate_value(lines[0], "faded")
            else:
                if sys.stdout.isatty() and self._coloured:
                    values["message"] = lines[0]
                else:
                    values["message"] = strip_colours(lines[0])

        return self._fmt % values

class LoggingCtl:
    log_folder = ""
    display_handler = None
    recipe_handlers = (None,None)
    recipe_log_path = ""
    slaves = {}
    transmit_handler = None

    def __init__(self, debug=False, log_dir=None, log_subdir=""):
        if log_dir != None:
            self.log_folder = os.path.abspath(os.path.join(log_dir, log_subdir))
        else:
            self.log_folder = os.path.abspath(os.path.join(
                                                os.path.dirname(sys.argv[0]),
                                                './Logs',
                                                log_subdir))
        if not os.path.isdir(self.log_folder):
            self._clean_folder(self.log_folder)

        #the display_handler will display logs in the terminal
        self.display_handler = logging.StreamHandler(sys.stdout)
        self.display_handler.setFormatter(MultilineFormatter(coloured=True))
        if not debug:
            self.display_handler.setLevel(logging.INFO)
        else:
            if debug == 1:
                self.display_handler.setLevel(logging.DEBUG)
            else:
                self.display_handler.setLevel(logging.NOTSET)

        logger = logging.getLogger()
        logger.setLevel(logging.NOTSET)
        logger.addHandler(self.display_handler)

    def set_recipe(self, recipe_path, clean=True, expand=""):
        recipe_name = os.path.splitext(os.path.split(recipe_path)[1])[0]
        if expand != "":
            recipe_name += "_" + expand
        self.recipe_log_path = os.path.join(self.log_folder, recipe_name)
        if clean:
            self._clean_folder(self.recipe_log_path)

        (recipe_info, recipe_debug) = self._create_file_handler(
                                                        self.recipe_log_path)
        logger = logging.getLogger()
        #remove handlers of the previous recipe
        logger.removeHandler(self.recipe_handlers[0])
        logger.removeHandler(self.recipe_handlers[1])

        self.recipe_handlers = (recipe_info, recipe_debug)
        logger.addHandler(recipe_info)
        logger.addHandler(recipe_debug)

    def unset_recipe(self):
        logger = logging.getLogger()
        logger.removeHandler(self.recipe_handlers[0])
        logger.removeHandler(self.recipe_handlers[1])
        self.recipe_handlers = (None, None)

    def add_slave(self, slave_id, name):
        slave_log_path = os.path.join(self.recipe_log_path, name)
        self._clean_folder(slave_log_path)

        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.propagate = True

        (slave_info, slave_debug) = self._create_file_handler(slave_log_path)
        logger.addHandler(slave_info)
        logger.addHandler(slave_debug)

        self.slaves[slave_id] = (name, slave_info, slave_debug)

    def remove_slave(self, slave_id):
        logger = logging.getLogger(self.slaves[slave_id][0])
        logger.propagate = False

        logger.removeHandler(self.slaves[slave_id][1])
        logger.removeHandler(self.slaves[slave_id][2])

        del self.slaves[slave_id]

    def add_client_log(self, slave_id, log_record):
        name = self.slaves[slave_id][0]
        logger = logging.getLogger(name)

        log_record['address'] = '(' + name + ')'
        record = logging.makeLogRecord(log_record)
        logger.handle(record)

    def set_connection(self, target):
        if self.transmit_handler != None:
            self.cancel_connection()
        self.transmit_handler = TransmitHandler(target)

        logger = logging.getLogger()
        logger.addHandler(self.transmit_handler)

        for k in self.slaves.keys():
            self.remove_slave(k)

    def cancel_connection(self):
        if self.transmit_handler != None:
            logger = logging.getLogger()
            logger.removeHandler(self.transmit_handler)
            del self.transmit_handler

    def disable_logging(self):
        self.cancel_connection()

        for s in self.slaves.keys():
            self.remove_slave(s)

        self.unset_recipe()
        logger = logging.getLogger()
        logger.removeHandler(self.display_handler)
        self.display_handler = None

    def _clean_folder(self, path):
        try:
            shutil.rmtree(path)
        except OSError as e:
            if e.errno != 2:
                raise
        os.makedirs(path)

    def _create_file_handler(self, folder_path):
        file_debug = logging.FileHandler(os.path.join(folder_path, 'debug'))
        file_debug.setFormatter(MultilineFormatter())
        file_debug.setLevel(logging.DEBUG)

        file_info = logging.FileHandler(os.path.join(folder_path, 'info'))
        file_info.setFormatter(MultilineFormatter())
        file_info.setLevel(logging.INFO)

        return (file_debug, file_info)

    def get_recipe_log_path(self):
        return self.recipe_log_path
