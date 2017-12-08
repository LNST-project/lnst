/*
 * sockopt_membership.c - IP_ADD/DROP_MEMBERSHIP socket option test
 * Copyright (C) 2012 Red Hat Inc.
 *
 * Author: Radek Pazdera (rpazdera@redhat.com)
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
 * 02110-1301, USA.
 */

#include "sockopt_utils.h"


void test_add_membership()
{
	struct ip_mreq mreq;
	mreq.imr_multiaddr.s_addr = inet_addr("127.0.0.1");
	struct ip_mreqn mreqn;

	test_setsockopt_error("IP_ADD_MEMBERSHIP Bad multicast address",
			IP_ADD_MEMBERSHIP, &mreq, sizeof(mreq), EINVAL);

	test_setsockopt_error("IP_ADD_MEMBERSHIP Bad optlen",
			IP_ADD_MEMBERSHIP, &mreq, 5, EINVAL);

	mreqn.imr_multiaddr.s_addr = inet_addr("239.1.2.3");
	mreqn.imr_address.s_addr = inet_addr("255.255.255.255");
	mreqn.imr_ifindex = 500;
	test_setsockopt_error("IP_ADD_MEMBERSHIP No device found",
			IP_ADD_MEMBERSHIP, &mreqn, sizeof(mreqn), ENODEV);
}

void test_drop_membership()
{
	struct ip_mreq mreq;
	mreq.imr_multiaddr.s_addr = inet_addr("127.0.0.1");
	mreq.imr_interface.s_addr = inet_addr("127.0.0.1");

	test_setsockopt_error("IP_DROP_MEMBERSHIP Bad optlen",
			IP_DROP_MEMBERSHIP, &mreq, 5, EINVAL);
	test_setsockopt_error("IP_DROP_MEMBERSHIP Bad multicast address",
			IP_DROP_MEMBERSHIP, &mreq, sizeof(mreq), EADDRNOTAVAIL);

	mreq.imr_multiaddr.s_addr = inet_addr("239.1.2.3");
	mreq.imr_interface.s_addr = inet_addr("127.0.0.1");
	test_setsockopt_error("IP_DROP_MEMBERSHIP Not a member",
			IP_DROP_MEMBERSHIP, &mreq, sizeof(mreq), EADDRNOTAVAIL);
}

int main()
{
	initialize();

	test_add_membership();
	test_drop_membership();

	report_and_exit();
	return 0;
}
