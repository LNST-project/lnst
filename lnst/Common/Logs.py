"""
Utils for logging.

Copyright 2011 Red Hat, Inc.
Licensed under the GNU General Public License, version 2 as
published by the Free Software Foundation; see COPYING for details.
"""

__author__ = """
jzupka@redhat.com (Jiri Zupka)
"""
import os, sys, shutil
from logging import Formatter
import logging.handlers
import traceback
from lnst.Common.LoggingHandler import TransmitHandler, ExportHandler
from lnst.Common.Colours import decorate_with_preset, strip_colours

def log_exc_traceback():
    cmd_type, value, tb = sys.exc_info()
    exception = traceback.format_exception(cmd_type, value, tb)
    logging.debug(''.join(exception))

class MultilineFormatter(Formatter): # addr:17 level:7
    _ADDR_WIDTH  = 17
    _NETNS_WIDTH = 8
    _LEVEL_WIDTH = 7
    _coloured    = False

    def __init__(self, coloured=False):
        fmt = "%(asctime)s %(address)s %(netns)s %(levelname)s: %(message)s"
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
            addr = "(localhost)"
        else:
            addr = "(" + record.address + ")"

        addr = addr.rjust(self._ADDR_WIDTH)
        return self._decorate_value(addr, "log_header")

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

        try:
            values["netns"] = record.__dict__["origin_name"]
        except:
            values["netns"] = "-"
        values["netns"] = values["netns"].rjust(self._NETNS_WIDTH)

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
    export_handler = None
    recipe_handlers = (None,None)
    recipe_log_path = ""
    slaves = {}
    transmit_handler = None
    _id_seq = 0
    log_list = {}

    def __init__(self, debug=False, log_dir=None, log_subdir="", colours=True):
        #clear any previously set handlers
        logger = logging.getLogger('')
        for i in list(logger.handlers):
            logger.removeHandler(i)
        for key, logger in list(logging.Logger.manager.loggerDict.items()):
            if type(logger) != type(logging.Logger):
                continue
            for i in list(logger.handlers):
                logger.removeHandler(i)

        self._origin_name = None

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
        self.display_handler.setFormatter(MultilineFormatter(colours))

        # the export_handler will add log messages to lists, so it could be exported to .lrc file
        self.log_list["controller"] = []
        self.export_handler = self._create_export_handler(self.log_list["controller"], colours)
        self.export_handler.setLevel(logging.DEBUG)

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
        logger.addHandler(self.export_handler)

    def unset_formatter(self):
        self.display_handler.setFormatter(None)
        self.export_handler.setFormatter(None)

    def _gen_index(self, increment=True):
        if increment:
            self._id_seq += 1
        return "%02d" % self._id_seq

    def set_recipe(self, recipe_path, clean=True, prepend=False, expand=""):
        recipe_name = os.path.splitext(os.path.split(recipe_path)[1])[0]
        if expand != "":
            recipe_name += "_" + expand
        if prepend:
            if expand == "match_1":
                recipe_name = self._gen_index() + "_" + recipe_name
            else:
                recipe_name = self._gen_index(increment=False) + "_" + recipe_name

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

    def add_slave(self, slave_id):
        slave_log_path = os.path.join(self.recipe_log_path, slave_id)
        self._clean_folder(slave_log_path)

        logger = logging.getLogger(slave_id)
        logger.setLevel(logging.DEBUG)
        logger.propagate = True

        (slave_info, slave_debug) = self._create_file_handler(slave_log_path)
        logger.addHandler(slave_info)
        logger.addHandler(slave_debug)

        self.log_list[slave_id] = []
        export_handler = self._create_export_handler(self.log_list[slave_id])
        logger.addHandler(export_handler)

        self.slaves[slave_id] = (slave_info, slave_debug, export_handler)

    def remove_slave(self, slave_id):
        logger = logging.getLogger(slave_id)
        logger.propagate = False

        logger.removeHandler(self.slaves[slave_id][0])
        logger.removeHandler(self.slaves[slave_id][1])
        logger.removeHandler(self.slaves[slave_id][2])

        del self.slaves[slave_id]

    def add_client_log(self, slave_id, log_record):
        logger = logging.getLogger(slave_id)

        log_record['address'] = slave_id
        record = logging.makeLogRecord(log_record)
        logger.handle(record)

    def set_connection(self, target):
        if self.transmit_handler != None:
            self.cancel_connection()
        self.transmit_handler = TransmitHandler(target)

        self.transmit_handler.set_origin_name(self._origin_name)

        logger = logging.getLogger()
        logger.addHandler(self.transmit_handler)

        for k in list(self.slaves.keys()):
            self.remove_slave(k)

    def cancel_connection(self):
        if self.transmit_handler != None:
            logger = logging.getLogger()
            logger.removeHandler(self.transmit_handler)
            del self.transmit_handler

    def disable_logging(self):
        self.cancel_connection()

        for s in list(self.slaves.keys()):
            self.remove_slave(s)

        self.unset_recipe()
        logger = logging.getLogger()
        logger.removeHandler(self.display_handler)
        logger.removeHandler(self.export_handler)
        self.display_handler = None
        self.export_handler = None

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

    def _create_export_handler(self, target: list, colours: bool = False):
        export_handler = ExportHandler(target)
        export_handler.setFormatter(MultilineFormatter(colours))

        return export_handler

    def get_recipe_log_path(self):
        return self.recipe_log_path

    def get_recipe_log_list(self):
        return self.log_list

    def set_origin_name(self, name):
        self._origin_name = name
        if self.transmit_handler != None:
            self.transmit_handler.set_origin_name(name)

    def print_log_dir(self):
        logging.info("Logs are stored in '%s'" % self.log_folder)
