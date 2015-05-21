from lnst.Controller.Task import ctl

hostA = ctl.get_host("machine1")
hostB = ctl.get_host("machine2")

hostA.sync_resources(modules=["IcmpPing", "Netperf"])
hostB.sync_resources(modules=["IcmpPing", "Netperf"])

ping_mod = ctl.get_module("IcmpPing",
             options={
               "addr": hostB.get_ip("testiface", 0),
               "count": 1000,
               "interval": 0.1,
               "iface" : hostA.get_devname("testiface")})

netserver = ctl.get_module("Netperf",
              options={
                "role" : "server",
                "bind" : hostA.get_ip("testiface")})

netperf_tcp = ctl.get_module("Netperf",
                options={
                  "role" : "client",
                  "netperf_server" : hostA.get_ip("testiface"),
                  "duration" : 60,
                  "testname" : "TCP_STREAM",
                  "netperf_opts" : "-L %s" % hostB.get_ip("testiface")})

netperf_udp= ctl.get_module("Netperf",
               options={
                 "role" : "client",
                 "netperf_server" : hostA.get_ip("testiface"),
                 "duration" : 60,
                 "testname" : "UDP_STREAM"})

hostA.run(ping_mod, timeout=500)
server_proc = hostA.run(netserver, bg=True)
ctl.wait(2)
hostB.run(netperf_tcp, timeout=100)
hostB.run(netperf_udp, timeout=100)
server_proc.intr()
