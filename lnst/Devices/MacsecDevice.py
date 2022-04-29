from lnst.Common.ExecCmd import exec_cmd
from lnst.Common.DeviceError import DeviceConfigError
from lnst.Devices.SoftDevice import SoftDevice

class MacsecDevice(SoftDevice):
    _name_template = "t_macsec"
    _cmd = ''

    def __init__(self, ifmanager, **kwargs):
        super(MacsecDevice, self).__init__(ifmanager)
        self._kwargs = kwargs

    def _create(self):
        realdev = self._kwargs.pop("realdev")
        encrypt = self._kwargs.pop("encrypt", None)
        cmd = "ip link add link %s %s type macsec" % (realdev.name, self.name)
        if encrypt:
            cmd += " encrypt %s" % encrypt
        exec_cmd(cmd)

    def rx(self, op, **kwargs):
        self._sci(op, kwargs)
        if op != 'del':
            try:
                self._cmd += "%s" % kwargs.pop('enable')
            except KeyError:
                pass
        self._chk_exec(op, kwargs)

    def rx_sa(self, op, **kwargs):
        self._sci(op, kwargs)
        self._sa_pn_key(op, kwargs)

    def tx_sa(self, op, **kwargs):
        self._cmd = "ip macsec %s %s tx " % (op, self.name)
        self._sa_pn_key(op, kwargs)

    def _sci(self, op, kwargs):
        self._cmd = "ip macsec %s %s rx " % (op, self.name)
        try:
            self._cmd += "sci %s " % kwargs.pop('sci')
        except KeyError:
            self._cmd += "port %s address %s " % (kwargs.pop('port'),
                                                  kwargs.pop('address'))

    def _sa_pn_key(self, op, kwargs):
        self._cmd += "sa %s " % kwargs.pop('sa')
        if op != 'del':
            try:
                self._cmd += "pn %s " % kwargs.pop('pn')
                self._cmd += "%s " % kwargs.pop('enable')
            except KeyError:
                pass
        if op == 'add':
            self._cmd += "key %s " % kwargs.pop('id')
            self._cmd += "%s" % kwargs.pop('key')
        self._chk_exec(op, kwargs)

    def _chk_exec(self, op, kwargs):
        if kwargs:
            raise DeviceConfigError("Unexpected options with %s: %s" % (op, kwargs))
        exec_cmd(self._cmd)
