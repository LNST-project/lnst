import sys
from lnst.Controller.Task import ctl

m1 = ctl.get_host("m1")
m2 = ctl.get_host("m2")

m1.run("[ \"%s\" == \"value1\" ]" % ctl.get_alias("alias1"))
m2.run("[ \"%s\" == \"value2\" ]" % ctl.get_alias("alias2"))

