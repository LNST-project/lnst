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

def log_exc_traceback():
    cmd_type, value, tb = sys.exc_info()
    exception = traceback.format_exception(cmd_type, value, tb)
    logging.debug(''.join(exception))


class MultilineFormater(Formatter):
    """
    Better formating of multiline logs.
    """
    def __init__(self, fmt=None, datefmt=None, linefmt=None):
        Formatter.__init__(self, fmt, datefmt)
        if linefmt:
            self.linefmt = linefmt
        else:
            self.linefmt = ""

    def format(self, record):
        """
        Format the specified record as text.

        The record's attribute dictionary is used as the operand to a
        string formatting operation which yields the returned string.
        Before formatting the dictionary, a couple of preparatory steps
        are carried out. The message attribute of the record is computed
        using LogRecord.getMessage(). If the formatting string uses the
        time (as determined by a call to usesTime(), formatTime() is
        called to format the event time. If there is exception information,
        it is formatted using formatException() and appended to the message.
        """
        record.message = record.getMessage()
        if not "address" in record.__dict__:
            record.address = "(127.0.0.1)"
        if self._fmt.find("%(asctime)") >= 0:
            record.asctime = self.formatTime(record, self.datefmt)
        lines = record.__dict__["message"].split("\n")
        s = ""
        if len(lines) > 1:
            record.__dict__['message'] = ""
            for line in lines:
                s += "\n" + self.linefmt + line
        s = self._fmt % record.__dict__ + s
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            try:
                s = s + record.exc_text
            except UnicodeError:
                # Sometimes filenames have non-ASCII chars, which can lead
                # to errors when s is Unicode and record.exc_text is str
                # See issue 8924
                s = s + record.exc_text.decode(sys.getfilesystemencoding())
        return s

class LoggingCtl:
    log_folder = ""
    formatter = None
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


        self.formatter = MultilineFormater(
                            '%(asctime)s| %(address)17.17s| %(levelname)5.5s: '
                            '%(message)s', '%Y-%m-%d %H:%M:%S', " "*4)


        #the display_handler will display logs in the terminal
        self.display_handler = logging.StreamHandler(sys.stdout)
        self.display_handler.setFormatter(self.formatter)
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

        del slaves[slave_id]

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
        file_debug.setFormatter(self.formatter)
        file_debug.setLevel(logging.DEBUG)

        file_info = logging.FileHandler(os.path.join(folder_path, 'info'))
        file_info.setFormatter(self.formatter)
        file_info.setLevel(logging.INFO)

        return (file_debug, file_info)
