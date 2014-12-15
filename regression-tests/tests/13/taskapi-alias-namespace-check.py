import sys
from lnst.Controller.Task import ctl

m1 = ctl.get_host("m1")

# this should fail
m1.run("[ \"%s\" == \"value1\" ]" % ctl.get_alias("foo"))

