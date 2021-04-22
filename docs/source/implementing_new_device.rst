==========================================
How to implement a new network device type
==========================================

This guide will explain how to extend the LNST with a new network device type.

Each device type supported by LNST is implemented as a separate class in
:mod:`lnst.Devices` module.

User can import such device using the following code:

.. code-block:: python

    from lnst.Devices import VlanDevice

To implement a class for new network device type several steps need to be done.

This guide will use **gre** tunnel device as an example.

.. contents:: :local:

SoftDevice class
----------------

All virtual devices should inherit from the :any:`SoftDevice` class.

.. code-block:: python

    from lnst.Devices.SoftDevice import SoftDevice

    class GreDevice(SoftDevice):
        pass

Device name template
--------------------

The new device class should define the name template for the created devices.
If the template is not defined a generic one defined by the :any:`SoftDevice`
class will be used instead.

.. code-block:: python

    from lnst.Devices.SoftDevice import SoftDevice

    class GreDevice(SoftDevice):
        _name_template = "t_gre"

Device type
-----------

User must also define the device type through the ``_link_type`` class attribute.
The value matches the link type that is used by iproute2's ``ip link`` utility.

For example, the gre device is created by following command:

.. code-block:: shell

    ip link add new_gre_device type gre remote 192.168.200.2

The `type gre` part of the command above should be used in the ``_link_type``.

For other link types user can check the output of the following command:

.. code-block:: shell

    ip link help
    ip -6 link help # for ipv6 specific devices

So, the device code will look like this:

.. code-block:: python

    from lnst.Devices.SoftDevice import SoftDevice

    class GreDevice(SoftDevice):
        _name_template = "t_gre"
        _link_type = "gre"

Device parameters
-----------------

The device class may define any parameters available for the network device type.

For example, the **gre** device uses the **local** and **remote** parameters
as in the following command:

.. code-block:: shell

    ip link add new_gre_device type gre local 192.168.100.1 remote 192.168.200.2

These parameters have to be defined as class properties with their setters.
They have to use :any:`SoftDevice` methods to configure the device's
parameters through kernel's netlink API:

- ``_get_linkinfo_data_attr()``
- ``_set_linkinfo_data_attr()`` for the property setters

The code extended with the **remote** parameter would look like this:

.. code-block:: python

    @property
    def remote(self):
        try:
            return ipaddress(self._get_linkinfo_data_attr("IFLA_GRE_LOCAL"))
        except:
            return None

    @remote.setter
    def remote(self, val):
        self._set_linkinfo_data_attr("IFLA_GRE_LOCAL", str(ipaddress(val)))
        self._nl_link_sync("set")

In the code above the ``remote`` property returns an IP address retrieved
through the netlink by calling the :meth:`_get_linkinfo_data_attr()` with the
netlink's representation of the **remote** parameter, that is **IFLA_GRE_LOCAL**.

The ``remote.setter`` configures the **remote** device parameter by calling
the :meth:`_set_linkinfo_data_attr()` with the netlink's representation of the
parameter **IFLA_GRE_LOCAL** and the IP address as the value of the parameter.

The setters must always include call of the :meth:`_nl_link_sync()` to commit
the changes through netlink.

For the device specific ``IFLA_*`` strings refer to `Finding out the IFLA_* strings`_

With the code above the user can now use the device class in a recipe,
for example:

.. code-block:: python

    from lnst.Controller import Controller, HostReq, DeviceReq, BaseRecipe
    from lnst.Devices.GreDevice import GreDevice

    class GreRecipe(BaseRecipe):
        machine1 = HostReq()
        machine1.nic1 = DeviceReq(label="net1")

        def test(self):
            machine1.gre = GreDevice(remote="192.168.200.2")

    ctl = Controller()
    recipe_instance = GreRecipe()
    ctl.run(recipe_instance)

Explanation of the netlink update bulking in LNST
-------------------------------------------------

Feel free to skip this section if you're not interested in the deeper
understanding of the device configuration in LNST.

In the previous section I stated that the device parameter's setters must
include the :meth:`_nl_link_sync()` method call to propagate the changes to
the kernel through netlink.

We might assume that configuration of a device parameter is done instantly,
by immediately sending the update to the netlink. This however does not
work when multiple parameters are required while the device is created.
Additionally we want to avoid unnecessary multiple calls to the netlink.

LNST solves this problem by using a bulk mode for the netlink updates.
In short, the bulk mode is postponing of sending the netlink updates for a
device until a bulk transfer is explicitly requested with
``_nl_link_sync(bulk=True)``.

Each :any:`SoftDevice` has bulk mode automatically enabled in the ``__init__()``
phase, so that specifying of multiple device parameters during instantiation
would generate just one netlink message to create the device.

The bulk mode is disabled once the device is created. After that changing
any of the properties would immediately result in propagation through the
netlink.

More information about the bulking concept is described in this
`commit <https://github.com/LNST-project/lnst/commit/e9f1d2a5722c7a4067649fc81ef3cb916944da69>`_


Mandatory device parameters
---------------------------

A device may require some parameters to be specified, for example a **gre**
device requires **remote** parameter.

You can specify such parameters in the class attribute ``_mandatory_params``:

.. code-block:: python

    class GreDevice(SoftDevice):
        _name_template = "t_gre"
        _link_type = "gre"
        _mandatory_opts = ["remote"]

LNST will automatically check if the mandatory parameters where specified
in the device instance and report back a failure.

Finding out the IFLA_* strings
------------------------------

The device parameters are configured through the kernel's netlink API.

In the code above we have mentioned two :any:`SoftDevice` methods used for
setting or retrieving the device parameters, the :meth:`_get_linkinfo_data_attr()`
and :meth:`_set_linkinfo_data_attr()`. Both methods takes a name of the device
parameter as an argument, these are prefixed with **IFLA_** string.

What becomes challenging is to find out the corresponding ``IFLA_*`` strings
for a specific network device. These are unique for each device.

Here the **pyroute2** comes handy. The pyroute2 is a Python module that
provides also an API for interacting with the kernel's netlink. LNST uses
this module for the device management.

To find out what parameters are needed to configure the test device simply
follow the procedure below.

Save the following code to file named watch_netlink.py

.. code-block:: python

    from pyroute2 import IPRoute
    from pprint import pprint

    with IPRoute() as ipr:
        while True:
            ipr.bind()
            for message in ipr.get():
                pprint(message)

Run the script in background and run an iproute command to create a gre
tunnel device (or any other device of your interest).

.. code-block:: shell

    ./watch_netlink.py &

    ip link add mygre type gre local 192.168.200.1 remote 192.168.200.2

The ``watch_netlink.py`` script should print the complete netlink message
including the details of ``IFLA_LINKINFO``. So simply find the message that
contains ``('IFLA_IFNAME', 'mygre')`` (**mygre** matches the device name used
in the ``ip link`` command above).

.. code-block::
    :emphasize-lines: 2,27

    {'__align': (),
     'attrs': [('IFLA_IFNAME', 'mygre'),
               ('IFLA_TXQLEN', 1000),
               ('IFLA_OPERSTATE', 'DOWN'),
               ('IFLA_LINKMODE', 0),
               ('IFLA_MTU', 1476),
               ('UNKNOWN', {'header': {'length': 8, 'type': 50}}),
               ('UNKNOWN', {'header': {'length': 8, 'type': 51}}),
               ('IFLA_GROUP', 0),
               ('IFLA_PROMISCUITY', 0),
               ('IFLA_NUM_TX_QUEUES', 1),
               ('IFLA_GSO_MAX_SEGS', 65535),
               ('IFLA_GSO_MAX_SIZE', 65536),
               ('IFLA_NUM_RX_QUEUES', 1),
               ('IFLA_CARRIER', 1),
               ('IFLA_QDISC', 'noop'),
               ('IFLA_CARRIER_CHANGES', 0),
               ('IFLA_PROTO_DOWN', 0),
               ('IFLA_CARRIER_UP_COUNT', 0),
               ('IFLA_CARRIER_DOWN_COUNT', 0),
               ('IFLA_MAP', {'mem_start': 0, 'mem_end': 0, 'base_addr': 0, 'irq': 0, 'dma': 0, 'port': 0}),
               ('IFLA_ADDRESS', 'c0:a8:c8:01:08:00'),
               ('IFLA_BROADCAST', 'c0:a8:c8:02:c4:00'),
               ('IFLA_STATS64', {'rx_packets': 0, 'tx_packets': 0, 'rx_bytes': 0, 'tx_bytes': 0, 'rx_errors': 0, 'tx_errors': 0, 'rx_dropped': 0, 'tx_dropped': 0, 'multicast': 0, 'collisions': 0, 'rx_length_errors': 0, 'rx_over_errors': 0, 'rx_crc_errors': 0, 'rx_frame_errors': 0, 'rx_fifo_errors': 0, 'rx_missed_errors': 0, 'tx_aborted_errors': 0, 'tx_carrier_errors': 0, 'tx_fifo_errors': 0, 'tx_heartbeat_errors': 0, 'tx_window_errors': 0, 'rx_compressed': 0, 'tx_compressed': 0}),
               ('IFLA_STATS', {'rx_packets': 0, 'tx_packets': 0, 'rx_bytes': 0, 'tx_bytes': 0, 'rx_errors': 0, 'tx_errors': 0, 'rx_dropped': 0, 'tx_dropped': 0, 'multicast': 0, 'collisions': 0, 'rx_length_errors': 0, 'rx_over_errors': 0, 'rx_crc_errors': 0, 'rx_frame_errors': 0, 'rx_fifo_errors': 0, 'rx_missed_errors': 0, 'tx_aborted_errors': 0, 'tx_carrier_errors': 0, 'tx_fifo_errors': 0, 'tx_heartbeat_errors': 0, 'tx_window_errors': 0, 'rx_compressed': 0, 'tx_compressed': 0}),
               ('IFLA_XDP', '05:00:02:00:00:00:00:00'),
               ('IFLA_LINKINFO', {'attrs': [('IFLA_INFO_KIND', 'gre'), ('IFLA_INFO_DATA', {'attrs': [('UNKNOWN', {'header': {'length': 5, 'type': 22}}), ('IFLA_GRE_LINK', 0), ('IFLA_GRE_IFLAGS', 0), ('IFLA_GRE_OFLAGS', 0), ('IFLA_GRE_IKEY', 0), ('IFLA_GRE_OKEY', 0), ('IFLA_GRE_LOCAL', '192.168.200.1'), ('IFLA_GRE_REMOTE', '192.168.200.2'), ('IFLA_GRE_TTL', 0), ('IFLA_GRE_TOS', 0), ('IFLA_GRE_PMTUDISC', 1), ('IFLA_GRE_FWMARK', 0), ('IFLA_GRE_ENCAP_TYPE', 0), ('IFLA_GRE_ENCAP_SPORT', 0), ('IFLA_GRE_ENCAP_DPORT', 0), ('IFLA_GRE_ENCAP_FLAGS', 0), ('IFLA_GRE_IGNORE_DF', 0)]})]}),
               ('IFLA_LINK', 0),
               ('UNKNOWN', {'header': {'length': 8, 'type': 54}}),
               ('IFLA_AF_SPEC', {'attrs': [('AF_INET', {'dummy': 65668, 'forwarding': 0, 'mc_forwarding': 0, 'proxy_arp': 0, 'accept_redirects': 1, 'secure_redirects': 1, 'send_redirects': 1, 'shared_media': 1, 'rp_filter': 0, 'accept_source_route': 1, 'bootp_relay': 0, 'log_martians': 0, 'tag': 0, 'arpfilter': 0, 'medium_id': 0, 'noxfrm': 0, 'nopolicy': 0, 'force_igmp_version': 0, 'arp_announce': 0, 'arp_ignore': 0, 'promote_secondaries': 0, 'arp_accept': 0, 'arp_notify': 0, 'accept_local': 0, 'src_vmark': 0, 'proxy_arp_pvlan': 0, 'route_localnet': 0, 'igmpv2_unsolicited_report_interval': 10000, 'igmpv3_unsolicited_report_interval': 1000})]})],
     'change': 0,
     'event': 'RTM_NEWLINK',
     'family': 0,
     'flags': 144,
     'header': {'error': None,
                'flags': 0,
                'length': 860,
                'pid': 0,
                'sequence_number': 0,
                'stats': Stats(qsize=0, delta=0, delay=0),
                'target': 'localhost',
                'type': 16},
     'ifi_type': 778,
     'index': 116,
     'state': 'down'}

So, inspecting the output above, the relevant ``IFLA_*`` strings are found
under **IFLA_LINKINFO** / **IFLA_INFO_DATA** (in highlighted lines):

- ``('IFLA_GRE_LOCAL', '192.168.200.1')``
- ``('IFLA_GRE_REMOTE', '192.168.200.2')``
