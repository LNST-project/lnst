from lnst.Controller.Task import ctl

m1 = ctl.get_host("testmachine1")

m1.sync_resources(modules=["Custom"], tools=[])

test = m1.run("for i in `seq 5`; do echo test; sleep 1; done", bg=True, save_output="yes")

test.wait()

output = test.get_result()["res_data"]["stdout"]

custom = ctl.get_module("Custom", options={ "fail": True })

if output.find("test") != -1:
    custom.update_options({ "fail": False})

m1.run(custom)
