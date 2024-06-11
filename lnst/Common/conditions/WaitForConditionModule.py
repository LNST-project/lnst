import time
import signal
import logging
from abc import abstractmethod

from ..BaseModule import BaseModule


class WaitForConditionModule(BaseModule):
    def __init__(self, timeout: int = 30, **kwargs):
        super().__init__(**kwargs)

        self._timeout = timeout

    @property
    def timeout(self):
        return self._timeout

    def run(self):
        logging.info(f"Waiting for condition {self.__class__.__name__} to be met")
        signal.signal(signal.SIGALRM, self._sig_handler)
        signal.alarm(self._timeout)

        counter = 0
        try:
            while not self._condition():
                time.sleep(1)
                logging.debug(f"Waiting for condition: {counter}/{self._timeout}")
                counter += 1
        except TimeoutError:
            logging.exception("Timeout of conditional wait reached!")
            return False
        finally:
            signal.alarm(0)
            logging.info(f"Condition {self.__class__.__name__} met/timeouted")

        return True

    @staticmethod
    def _sig_handler(signum, _):
        if signum == signal.SIGALRM:
            raise TimeoutError("Timeout reached")

        return

    @abstractmethod
    def _condition(self):
        pass
