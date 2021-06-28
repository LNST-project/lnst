import time
import socket
import logging
from lnst.Common.Logs import log_exc_traceback
from lnst.Common.SecureSocket import SecSocketException
from lnst.Controller.Machine import Machine
from lnst.Controller.Host import Host

class RecipeControl(object):
    def __init__(self, controller, recipe):
        self._controller = controller
        self._recipe = recipe

    @property
    def hosts(self):
        return self._controller._hosts

    def wait(self, sec):
        finish_time = time.time() + sec
        logging.info("Suspending recipe execution for {} seconds, "
                     "messages from slaves will still be processed.".
                     format(sec))

        def condition():
            return time.time() > finish_time

        msg_dispatcher = self._controller._msg_dispatcher
        msg_dispatcher.wait_for_condition(condition)

    def wait_for_condition(self, condition, timeout=0):
        #TODO add descriptions to conditions?
        logging.info("Suspending recipe execution until condition is true")

        msg_dispatcher = self._controller._msg_dispatcher
        msg_dispatcher.wait_for_condition(condition, timeout)

    def connect_host(self, hostname, timeout=60, port=None, machine_id=None,
                     security=None):
        ctl_config = self._controller._config
        msg_dispatcher = self._controller._msg_dispatcher

        if security is None:
            security = {"auth_type": "none"}

        if machine_id is None:
            machine_id = hostname

        m = Machine(machine_id, hostname, msg_dispatcher,
                    ctl_config, None, port, security)

        def condition():
            try:
                m.init_connection(timeout=1)
                return True
            except:
                log_exc_traceback()
                return False

        msg_dispatcher.wait_for_condition(condition, timeout)

        host = Host(m)
        self._controller._prepare_machine(m)
        m.start_recipe(self._recipe)
        return host
