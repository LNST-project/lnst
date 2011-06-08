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

LOCAL_IP = "(127.0.0.1)"

class FindRootPathError(Exception):
    def __init__(self, path, rootFolder):
            Exception.__init__(self, path, rootFolder)
            self.path = path
            self.rootFolder = rootFolder

    def __str__(self):
        return ("Cannot find root folder '%s' in path '%s'" %
                (self.rootFolder, self.path))


def find_test_root(path, rootFolder):
    """
    Find test root folder in path.

    @param path: Path.
    @param rootFolder: Name of test root folder.
    @return: Absolute path to test root folder.
    """
    sub = None
    path = os.path.abspath(path)
    _path = path
    while sub != rootFolder and sub != '':
        _path, sub = os.path.split(_path)
    if sub != rootFolder:
        raise FindRootPathError(path, rootFolder)
    return os.path.join(_path, sub)


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
    log_root = None
    logFolder = None
    logger = None
    root_path = None
    debug = None
    date = None
    nameExtend = None
    @classmethod
    def __init__(cls,debug=0, waitForNet=False, logger=logging.getLogger(),
                 recipe_path=None, log_root="Logs", to_display=True, date=None,
                 nameExtend=None):
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
        cls.log_root = log_root
        cls.logFolder = os.path.dirname(sys.argv[0])
        cls.logger = logger
        cls.debug = debug
        cls.date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        cls.nameExtend = nameExtend
        cls.root_path = cls.prepare_logging(debug, waitForNet,
                                            recipe_path, to_display)


    @staticmethod
    def append_network_hadler(address, port):
        """
        Append to log network handler.
        """
        logging.net_handler.setTarget(logging.handlers.SocketHandler(address, port))

    @classmethod
    def clean_root_log_folder(cls, logRootPath):
        try:
            shutil.rmtree(logRootPath)
        except OSError, e:
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
        cls.root_path = os.path.join(cls.logFolder, cls.log_root,
                                    cls.date+cls.nameExtend, recipe_name)
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
            memory_handler = logging.handlers.MemoryHandler(1)
            root_logger.addHandler(memory_handler)
            logging.net_handler = memory_handler

        log_root_folder = cls.set_logging_root_path(recipe_path)

        root_logger.setLevel(logging.NOTSET)
        sys.stdout = LoggingFile(level=logging.INFO)
        sys.stderr = LoggingFile(level=logging.ERROR)
        return log_root_folder
