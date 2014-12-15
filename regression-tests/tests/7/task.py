from lnst.Controller.Task import ctl

m1 = ctl.get_host("1")
m2 = ctl.get_host("2")

devname = m1.get_devname("testiface")
hwaddr = m1.get_hwaddr("testiface")

m1.run("echo 1_%s_" % hwaddr)

m1.run("echo `ip link show %s | grep -o '    link/ether \([0-9a-fA-F]\{2\}:\?\)\{6\}' | cut -c 16-` >/tmp/lnst-hwaddr" % devname)
m1.run("ip l set %s address 52:54:00:12:34:56" % devname)
ctl.wait(2)

m1.run("echo 2_%s_" % hwaddr)
m1.run("ip l set %s address `cat /tmp/lnst-hwaddr`" % devname)

ctl.wait(2)

m1.run("echo 3_%s_`cat /tmp/lnst-hwaddr | tr '[:lower:]' '[:upper:]'`_" % hwaddr)

m1.run("rm -f /tmp/lnst-hwaddr")

