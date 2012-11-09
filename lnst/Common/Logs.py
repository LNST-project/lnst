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

LOCAL_IP = "(127.0.0.1)"

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
            record.address = LOCAL_IP
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


class stdLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        logging.Logger.__init__(self, name, level)

    def findCaller(self):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.
        """
        rv = "stdio", 0, "(unknown function)"
        return rv

logging._acquireLock()
try:
    logging.setLoggerClass(stdLogger)
    logging.getLogger("root.stdLogger")
    logging.setLoggerClass(logging.Logger)
finally:
    logging._releaseLock()


class LoggingFile(object):
    """
    File-like object that will receive messages pass them to the logging
    infrastructure in an appropriate way.
    """
    def __init__(self, prefix='', level=logging.DEBUG):
        """
        @param prefix - The prefix for each line logged by this object.
        """
        self._prefix = prefix
        self._level = level
        self._buffer = []
        self._stdLogger = logging.getLogger("root.stdLogger")


    def write(self, data):
        """"
        Writes data only if it constitutes a whole line. If it's not the case,
        store it in a buffer and wait until we have a complete line.
        @param data - Raw data (a string) that will be processed.
        """
        # splitlines() discards a trailing blank line, so use split() instead
        data_lines = data.split('\n')
        if len(data_lines) > 1:
            self._buffer.append(data_lines[0])
            self._flush_buffer()
        for line in data_lines[1:-1]:
            self._log_line(line)
        if data_lines[-1]:
            self._buffer.append(data_lines[-1])


    def _log_line(self, line):
        """
        Passes lines of output to the logging module.
        """
        self._stdLogger.log(self._level, self._prefix + line)


    def _flush_buffer(self):
        if self._buffer:
            self._log_line(''.join(self._buffer))
            self._buffer = []


    def flush(self):
        self._flush_buffer()


class Logs:
    file_handlers = []
    formatter = None
    logFolder = None
    logger = None
    root_path = None
    debug = None
    date = None
    nameExtend = None
    @classmethod
    def __init__(cls,debug=0, waitForNet=False, logger=logging.getLogger(),
                 recipe_path=None, to_display=True, date=None,
                 nameExtend=None, log_folder=None):
        logging.addLevelName(5, "DEBUG2")
        logging.DEBUG2 = 5
        if nameExtend is None:
            nameExtend = ""
        else:
            nameExtend = "_" + nameExtend
        cls.file_handlers = []
        cls.formatter = MultilineFormater(
                            '%(asctime)s| %(address)17.17s%(module)15.15s'
                            ':%(lineno)4.4d| %(levelname)s: '
                            '%(message)s', '%d/%m %H:%M:%S', " "*4)
        if log_folder != None:
            cls.logFolder = log_folder
        else:
            cls.logFolder = os.path.join(os.path.dirname(sys.argv[0]), './Logs')
        cls.logger = logger
        cls.debug = debug
        if date is None:
            cls.date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        else:
            cls.date = date
        cls.nameExtend = nameExtend
        cls.root_path = cls.prepare_logging(debug, waitForNet,
                                            recipe_path, to_display)

    @classmethod
    def clean_root_log_folder(cls, logRootPath):
        try:
            shutil.rmtree(logRootPath)
        except OSError as e:
            if e.errno != 2:
                raise
        os.makedirs(logRootPath)

    @classmethod
    def _create_file_handler(cls, path):
        file_debug = logging.FileHandler(os.path.join(path, 'debug'))
        file_debug.setFormatter(cls.formatter)
        file_debug.setLevel(logging.NOTSET)

        file_info = logging.FileHandler(os.path.join(path, 'info'))
        file_info.setFormatter(cls.formatter)
        file_info.setLevel(logging.INFO)

        cls.file_handlers.append(file_debug)
        cls.file_handlers.append(file_info)
        return (file_debug, file_info)


    @classmethod
    def set_logging_root_path(cls, recipe_path=None, clean=True):
        """
        Change file handlers path.
        """

        if recipe_path is None:
            recipe_path = ""
        root_logger = cls.logger
        recipe_name = os.path.splitext(os.path.split(recipe_path)[1])[0]
        cls.root_path = os.path.join(cls.logFolder, cls.date+cls.nameExtend,
                                    recipe_name)
        if (clean):
            cls.clean_root_log_folder(cls.root_path)
        for fhandler in cls.file_handlers:
            root_logger.removeHandler(fhandler)
        del cls.file_handlers[:]

        (file_debug, file_info) = cls._create_file_handler(cls.root_path)
        root_logger.addHandler(file_debug)
        root_logger.addHandler(file_info)
        return cls.root_path


    @classmethod
    def get_logging_root_path(cls):
        return cls.root_path

    @classmethod
    def get_buffer(cls):
        return cls.buffer

    @classmethod
    def prepare_logging(cls, debug=0, waitForNet=False,
                        recipe_path=None, to_display=True):
        """
        Configure logging.

        @param debug: If True print to terminal debug level of logging messages.
        """
        root_logger = cls.logger
        if to_display:
            display = logging.StreamHandler()
            display.setFormatter(cls.formatter)
            if not debug:
                display.setLevel(logging.INFO)
            else:
                if debug == 1:
                    display.setLevel(logging.DEBUG)
                else:
                    display.setLevel(logging.NOTSET)
            root_logger.addHandler(display)

        if waitForNet:
            handler = LogBuffer()
            cls.buffer = handler
            root_logger.addHandler(handler)

        log_root_folder = cls.set_logging_root_path(recipe_path)

        root_logger.setLevel(logging.NOTSET)
        sys.stdout = LoggingFile(level=logging.INFO)
        sys.stderr = LoggingFile(level=logging.ERROR)
        return log_root_folder
