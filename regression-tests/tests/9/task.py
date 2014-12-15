from lnst.Controller.Task import ctl

m1 = ctl.get_host("1")
m2 = ctl.get_host("2")

ping_mod = ctl.get_module("IcmpPing", options={"addr": m2.get_ip("testiface", 0),
                          "count":40, "interval": 0.2, "limit_rate": 95})

ping_test = m1.run(ping_mod, timeout=30)
