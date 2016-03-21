from lnst.Controller.Task import ctl

m1 = ctl.get_host("testmachine1")

m1.sync_resources(modules=["Custom"], tools=[])

test = m1.run("while true; do echo test; sleep 1; done", bg=True, save_output="yes")

ctl.wait(5)

test.kill()
