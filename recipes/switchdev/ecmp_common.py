from time import sleep
from TestLib import TestLib

PKTGEN_COUNT=1000
PKTGEN_ROUNDS=2
PKTGEN_RATE="1MB"

def test_ip(major, minor, prefix=[24,64]):
    return ["192.168.1%d.%d%s" % (major, minor,
            "/" + str(prefix[0]) if len(prefix) > 0 else ""),
            "2002:%d::%d%s" % (major, minor,
            "/" + str(prefix[1]) if len(prefix) > 1 else "")]

def ipv4(test_ip):
    return test_ip[0]

def ipv6(test_ip):
    return test_ip[1]

def test_traffic(tl, from_if, to_if, ecmp_in_if, ecmp_ifaces, expected = 1.,
                 errmsg = "ecmp traffic"):
    reciever_thresh = 0.9 * PKTGEN_ROUNDS * PKTGEN_COUNT * expected
    ecmp_thresh = 0.7 * reciever_thresh / len(ecmp_ifaces)

    # run pktgen once to get all the needed arps for all the src ips
    tl.pktgen(from_if, to_if, 100, dst_mac = ecmp_in_if.get_hwaddr(),
              count = PKTGEN_COUNT, rate = PKTGEN_RATE,
              src_min = ipv4(test_ip(1, 100, [])),
              src_max = ipv4(test_ip(1, 200, [])))

    sleep(2)
    before_reciever_stats = to_if.link_stats()["rx_packets"]
    before_ecmp_stats = [i.link_stats()["tx_packets"] for i in ecmp_ifaces]

    for i in range(PKTGEN_ROUNDS):
        tl.pktgen(from_if, to_if, 100, dst_mac = ecmp_in_if.get_hwaddr(),
                  count = PKTGEN_COUNT, rate = PKTGEN_RATE,
                  src_min = ipv4(test_ip(1, 100, [])),
                  src_max = ipv4(test_ip(1, 200, [])))

    sleep(2)
    after_reciever_stats = to_if.link_stats()["rx_packets"]
    after_ecmp_stats = [i.link_stats()["tx_packets"] for i in ecmp_ifaces]

    reciever_stats = after_reciever_stats - before_reciever_stats
    ecmp_stats = [a - b for a, b in zip(after_ecmp_stats, before_ecmp_stats)]

    if reciever_stats < reciever_thresh:
        msg = "%s: pktgen receiver got %d < %d" % \
               (errmsg, reciever_stats, reciever_thresh)
        tl.custom(to_if.get_host(), "receiver", msg)

    for ecmp_stat in ecmp_stats:
        if ecmp_stat < ecmp_thresh:
            msg = "%s: ECMP link sent %d < %d" % \
                   (errmsg, ecmp_stat, ecmp_thresh)
            tl.custom(ecmp_ifaces[0].get_host(), "ECMP", msg)

def create_topology(from_if, ecmp_in_if, ecmp_tx_ifaces, ecmp_rx_ifaces,
                    ecmp_out_if, to_if, num_nexthops = None):
    """
    Helper function to create the simple ECMP topology:

                   +-------------------+   +--------------------+
                   |                   |   |                    |
                   |          ecmp_tx1 +---+  ecmp_rx1          |
    +--------+     |          ecmp_tx2 |---|  ecmp_rx2          |   +--------+
    |        |     |          ecmp_tx3 +---+  ecmp_rx3          |   |        |
    |   from +-----+ ecmp_in      .    |   |      .    ecmp_out +---+ to     |
    |        |     |              .    |   |      .             |   |        |
    +--------+     |              .    |   |      .             |   +--------+
                   |          ecmp_txn +---+  ecmp_rxn          |
                   |                   |   |                    |
                   +-------------------+   +--------------------+

    The function sets all the needed routes and ip addresses. If num nexthops is
    not specified, it is equal to the number of ecmp_links.
    """
    from_if.set_addresses(test_ip(1, 1))
    ecmp_in_if.set_addresses(test_ip(1, 2))
    nh_addrs = []

    if num_nexthops == None:
        num_nexthops = len(ecmp_rx_ifaces)

    for i, ecmp_if in enumerate(ecmp_tx_ifaces):
        ecmp_if.set_addresses(test_ip(i + 10, 2))

    ecmp_rx_ip_addresses = [[] for i in ecmp_rx_ifaces]
    for nexthop_index in range(num_nexthops):
        ecmp_if_index = nexthop_index % len(ecmp_rx_ifaces)
        nexthop_if_index = nexthop_index / len(ecmp_rx_ifaces)
        ecmp_if = ecmp_rx_ifaces[ecmp_if_index]
        ip_major = ecmp_if_index + 10
        ip_minor = 10 + nexthop_if_index
        ecmp_rx_ip_addresses[ecmp_if_index] += test_ip(ip_major, ip_minor)
        nh_addrs.append(test_ip(ip_major, ip_minor, []))

    for i, ecmp_if in enumerate(ecmp_rx_ifaces):
        ecmp_if.set_addresses(ecmp_rx_ip_addresses[i])

    ecmp_out_if.set_addresses(test_ip(2, 3))
    to_if.set_addresses(test_ip(2, 4))

    from_if.add_nhs_route(ipv4(test_ip(2,0)), [str(ecmp_in_if.get_ip(0))])
    ecmp_in_if.add_nhs_route(ipv4(test_ip(2,0)),
                             [str(ipv4(nh_addr)) for nh_addr in nh_addrs])
    ecmp_out_if.add_nhs_route(ipv4(test_ip(1,0)),
                              [str(i.get_ip(0)) for i in ecmp_tx_ifaces])
    to_if.add_nhs_route(ipv4(test_ip(1,0)), [str(ecmp_out_if.get_ip(0))])

    from_if.add_nhs_route(ipv6(test_ip(2,0)), [str(ecmp_in_if.get_ip(1))])
    ecmp_in_if.add_nhs_route(ipv6(test_ip(2,0)),
                             [str(ipv6(nh_addr)) for nh_addr in nh_addrs])
    ecmp_out_if.add_nhs_route(ipv6(test_ip(1,0)),
                              [str(i.get_ip(1)) for i in ecmp_tx_ifaces])
    to_if.add_nhs_route(ipv6(test_ip(1,0)), [str(ecmp_out_if.get_ip(1))])
