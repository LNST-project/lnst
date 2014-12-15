from lnst.Controller.Task import ctl

m = ctl.get_host("lb")

addr1 = m.get_ip("nic1")
addr2 = m.get_ip("nic2")

pfx1 = m.get_prefix("nic1")
pfx2 = m.get_prefix("nic2")

m.run("echo %s" % addr1)
m.run("echo %s" % addr2)
m.run("echo %s" % pfx1)
m.run("echo %s" % pfx2)

