from lnst.Controller.Task import ctl

hostA = ctl.get_host("machine1")
hostB = ctl.get_host("machine2")

hostA.sync_resources(modules=["IcmpPing"])
hostB.sync_resources(modules=["IcmpPing"])

hostA_devices = hostA.get_interface("testiface")
hostB_devices = hostB.get_interface("testiface")

ping_mod = ctl.get_module("IcmpPing",
                          options={
                             "addr": hostB.get_ip("testiface", 0),
                             "count": 100,
                             "interval": 0.2,
                             "limit_rate": 95})

hostA.run(ping_mod)
