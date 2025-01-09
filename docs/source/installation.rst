.. _installation:

Install LNST and Hello world
============================

LNST is logically split into two separate application use cases:

* Controller - something that controlls the execution of your :any:`Test
  Recipes<BaseRecipe>`
* Agent - a server application running on all hosts available for testing,
  executes remote procedure calls from the Controller to either run tests or
  configure the test machine

Codebases for both use cases are developed in this repository and as we
currently don't have a stable release yet, the recommended method of
installation is either to install both Agents and Controller on your
local machines or to use docker/podman. Manual installation on your 
machine involves the following steps:

.. code-block:: bash

    git clone https://github.com/LNST-project/lnst
    cd lnst
    poetry install


For installation of containerized version, see :ref:`containerized`.

This installs both the Controller and the Agent code, and you'll need to run
this on all the test machines that you want to use as well as the machine which
you want to use as the Controller. Optionally a Controller and a Agent CAN run
on the same machine.
Some of dependencies used across lnst are optional and could be installed using ``-E|--extras``
parameter of poetry.

Dependencies groups:

* required - installed automatically by ``poetry install`` command

  * ``pyroute2`` used to configure devices
  * ``lxml`` used to parse machine xml files. ``lxml`` as one of the few, supports Relax NG schema validation.

    * Required binary dependencies: ``libxml2`` and ``libxslt``
  * ``ethtool`` used to configure network devices

    * Required binary dependencies: ``libnl3-devel``, ``gcc``, ``python39-devel``
* optional - installed using ``poetry install -E [GROUP_NAME]``

  * ``virt`` - used for running lnst in virtual machines

    * Required binary dependencies: ``libvirt-devel``
  * ``containers`` - used for running lnst in containers

    * Required binary dependencies: ``podman``. Using Docker instead of Podman is not supported (yet).
  * ``sec_socket`` - used for secure communication between Controller and Agent(s)
  * ``trex`` - ``TRex`` recipes requires ``pyyaml`` and ``trex`` - needs to be installed manually (see official installation guide) as there is no official Python trex module

You can start your Agent application immediately by running::

    poetry run lnst-agent

Because the lnst-agent application takes care of network configuration, it
**requires** to be executed with root privileges. This is **A BIG SECURITY
RISK** so make sure you only run this application on test machines that are not
publicly accessible or don't contain any sensitive data.

The Controller is a bit more complicated and requires you to:

* create an executable test script
* create a agent machine pool


.. _hello-world-script:

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
            self.matched.machine1.nic1.ip_add("192.168.1.1/24")
            self.matched.machine1.nic1.up()
            self.matched.machine2.nic1.ip_add("192.168.1.2/24")
            self.matched.machine2.nic1.up()

            self.matched.machine1.run("ping 192.168.1.2")

    ctl = Controller()
    recipe_instance = HelloWorldRecipe()
    ctl.run(recipe_instance)


This test requires that you have 2 test machines that are directly connected to
each other.
If you write this into a ``hello_world.py`` file you should now be able to
execute this script by running::

    poetry run python3 hello_world.py

And you'll end up receiving an error about being unable to find a match in your
configured pools, since we didn't configure any yet, this is quite expected. But
running this script did take care of creating a default configuration file and
directory where we'll now be able to create our machine pool.


.. _machines-pool:

Creating a simple machine pool
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The default location for the Controller config file is ``~/.lnst/lnst-ctl.conf``.
At this point in time, you don't need to change anything inside this file.

At the same time, the default location for a machine pool is ``~/.lnst/pool/``,
to create a pool you'll need to put XML files that describe your test machines
where the ``lnst-agent`` application is running, and how they're connected. You
need to create one file per test machine, so to satisfy the
**HelloWorldRecipe** requirements, we need to create two files:

.. code-block:: bash

    touch ~/.lnst/pool/test_machine1.xml
    touch ~/.lnst/pool/test_machine2.xml

For the contents of the files you can use the following template:

.. code-block:: xml

    <agentmachine>
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
    </agentmachine>

You'll need to edit the template and replace the **HOSTNAME** and
**MAC_ADDRESS** strings with values that correspond to the hostname which the
controller can use to connect to the agent, and the mac address of a network
interface usable for testing. This **MUST** be a different interface than the
one used for the Controller-Agent connection, as it's configuration will change
during test execution, the Controller-Agent connection would break if you used
the same interface.

After creating your pool, you should now be able to run the ``hello_world.py``
script successfully and receive back some logs about what happened.

Note: At startup, You may receive some errors of the following form:

``ERROR: Command "ethtool -a virbr0" execution failed (exited with 76)``

LNST probes network devices using `ethtool` on initialization. If those
network devices do not support the specific `ethtool` command, you may
receive these benign error messages.

Run additional recipes
======================

LNST contains a number of recipe classes in ``lnst/Recipes``. These can be run by
writing an executable python script to create an instance of a Controller class
and an instance of the Test Recipe that we want to run, and calling the Controller.run()
method to execute it.

A minimal example of this for the ``NoVirtOvsVxlanRecipe`` recipe can be seen here:

.. code-block:: python

        from lnst.Controller import Controller, HostReq, DeviceReq, BaseRecipe
        from lnst.Recipes.ENRT import NoVirtOvsVxlanRecipe

        ctl = Controller()
        recipe_instance = NoVirtOvsVxlanRecipe(driver="lnst")
        ctl.run(recipe_instance)

It should be noted that some recipes may have some pre-requisites. For example, this
recipe required the ``iperf3`` package and OVS should be running or startable by
``systemctl start openvswitch.service``

This test requires that you have 2 test machines that are directly connected to
each other. This also shows an example of passing the `driver` parameter to the
test class. The `driver` parameter is used to modify the HW network requirements,
specifically to request Devices. You can see the corresponding parameter in the
XML definition of one of the two machines in the pool used in this test:

.. code-block:: xml

    <agentmachine>
        <params>
            <param name="hostname" value="HOSTNAME"/>
            <param name="rpc_port" value="9999"/>
        </params>
        <interfaces>
            <eth label="A" id="1">
                <params>
                    <param name="hwaddr" value="MAC_ADDRESS"/>
                    <param name="driver" value="lnst"/>
                </params>
            </eth>
        </interfaces>
    </agentmachine>

Additional parameters may be added to a recipe instantiation to configure the
recipe. Some parameters may be specific for a particular recipe and others may
apply to all recipes.

For example, for ``NoVirtOvsVxlanRecipe``:

.. code-block:: python

        recipe_instance = NoVirtOvsVxlanRecipe(driver="lnst", perf_tests=["tcp_stream", "udp_stream"], perf_msg_sizes=[1400])

``perf_tests`` specifies a list of perf tests to run for this recipe
``perf_mesg_sizes`` specifies the message size to send when doing performance tests

Other examples include:

``perf_duration`` specifies the duration of test runs
``perf_iterations`` specifies the number of iterations of a performance test to run

If you write all of this into a ``hello_world2.py`` file you should now be able to
execute this script by running::

    poetry run python3 hello_world2.py

If you have previously created your machine pool configuration (and added the driver
parameter as indicated above), the recipe should run to completion.

Debugging when things go wrong
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Additional debug information on the agents can be seen by running the ``lnst-agent``
application with the ``-d`` flag. Additional debug information on the controller can
be seen by adding the ``debug`` paramter to the instantiation of the ``controller``
class.

.. code-block:: bash

        ctl = Controller(debug=1)

Logs should also be saved in the ``Logs`` directory.

Printing summary information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also modify your ``hello_world2.py`` application to print summary information
at the end of the run:

.. code-block:: python

        from lnst.Controller import Controller, HostReq, DeviceReq, BaseRecipe
        from lnst.Recipes.ENRT import NoVirtOvsVxlanRecipe

        from lnst.Controller.RunSummaryFormatter import RunSummaryFormatter
        from lnst.Controller.RecipeResults import ResultLevel
        import logging

        ctl = Controller(debug=1)
        recipe_instance = NoVirtOvsVxlanRecipe(driver="lnst", perf_tests=["tcp_stream", "udp_stream"], perf_msg_sizes=[1400])
        ctl.run(recipe_instance)

        summary_fmt = RunSummaryFormatter(
            level=ResultLevel.IMPORTANT + 0, colourize=True
        )
        for run in recipe_instance.runs:
            logging.info(summary_fmt.format_run(run))
