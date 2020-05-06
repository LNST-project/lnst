Install LNST and Hello world
============================

LNST is logically split into two separate application use cases:

* Controller - something that controlls the execution of your :any:`Test
  Recipes<BaseRecipe>`
* Slave - a server application running on all hosts available for testing,
  executes remote procedure calls from the Controller to either run tests or
  configure the test machine

Codebases for both use cases are developed in this repository and as we
currently don't have a stable release yet, the recommended method of
installation involves the following steps:

.. code-block:: bash

    git clone https://github.com/LNST-project/lnst
    cd lnst
    pip3 install --requirement requirements.txt
    pip3 install .


This installs both the Controller and the Slave code, and you'll need to run
this on all the test machines that you want to use as well as the machine which
you want to use as the Controller. Optionally a Controller and a Slave CAN run
on the same machine.

You can start your Slave application immediatelly by running::

    lnst-slave

Because the lnst-slave application takes care of network configuration, it
**requires** to be executed with root privileges. This is **A BIG SECURITY
RISK** so make sure you only run this application on test machines that are not
publicly accessible or don't contain any sensitive data.

The Controller is a bit more complicated and requires you to:

* create an executable test script
* create a slave machine pool

Creating an executable "HelloWorld" test script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

LNST currently doesn't come with a CLI application for the Controller, instead
we need to create an executable python script ourselves that takes care of
creating an instance of a Controller class and an instance of the Test Recipe
that we want to run and calling the Controller.run() method to execute it.

A minimal "hello world" example of an executable test script looks like this:

.. code-block:: python

    from lnst.Controller import Controller, HostReq, DeviceReq, BaseRecipe

    class HelloWorldRecipe(BaseRecipe):
        machine1 = HostReq()
        machine1.nic1 = DeviceReq(label="net1")

        machine2 = HostReq()
        machine2.nic1 = DeviceReq(label="net1")

        def test(self):
            self.matched.m1.nic1.ip_add("192.168.1.1/24")
            self.matched.m1.nic1.up()
            self.matched.m2.nic1.ip_add("192.168.1.2/24")
            self.matched.m2.nic1.up()

            self.matched.m1.run("ping 192.168.1.2")

    ctl = Controller()
    recipe_instance = HelloWorldRecipe()
    ctl.run(recipe_instance)


This test requires that you have 2 test machines that are directly connected to
each other.
If you write this into a ``hello_world.py`` file you should now be able to
execute this script by running::

    python3 hello_world.py

And you'll end up receiving an error about being unable to find a match in your
configured pools, since we didn't configure any yet, this is quite expected. But
running this script did take care of creating a default configuration file and
directory where we'll now be able to create our machine pool.

Creating a simple machine pool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default location for the Controller config file is ``~/.lnst/lnst-ctl.conf``.
At this point in time, you don't need to change anything inside this file.

At the same time, the default location for a machine pool is ``~/.lnst/pool/``,
to create a pool you'll need to put XML files that describe your test machines
where the ``lnst-slave`` application is running, and how they're connected. You
need to create one file per test machine, so to satisfy the
**HelloWorldRecipe** requirements, we need to create two files:

.. code-block:: bash

    touch ~/.lnst/pool/test_machine1.xml
    touch ~/.lnst/pool/test_machine2.xml

For the contents of the files you can use the following template:

.. code-block:: xml

    <slavemachine>
        <params>
            <param name="hostname" value="HOSTNAME"/>
            <param name="rpc_port" value="9999"/>
        </params>
        <interfaces>
            <eth label="A" id="1">
                <params>
                    <param name="hwaddr" value="MAC_ADDRESS"/>
                </params>
            </eth>
        </interfaces>
    </slavemachine>

You'll need to edit the template and replace the **HOSTNAME** and
**MAC_ADDRESS** strings with values that correspond to the hostname which the
controller can use to connet to the slave, and the mac address of a network
interface usable for testing. This **MUST** be a different interface than the
one used for the Controller-Slave connection, as it's configuration will change
during test execution, the Controller-Slave connection would break if you used
the same interface.

After creating your pool, you should now be able to run the ``hello_world.py``
script successfully and receive back some logs about what happened.
