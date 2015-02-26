/*
 * sockopt_if.c - IP_MULTICAST_IF socket option test
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


void test_if()
{
	struct in_addr address;
	size_t size = sizeof(address);

	address.s_addr = INADDR_ANY;
	test_getsockopt("IP_MULTICAST_IF default value",
				IP_MULTICAST_IF, &address, size);

	address.s_addr = inet_addr("127.0.0.1");
	test_sockopt_value("IP_MULTICAST_IF set to 127.0.0.1",
				IP_MULTICAST_IF, &address, size);

	struct ip_mreqn mreqn;
	mreqn.imr_multiaddr.s_addr = inet_addr("239.1.2.3");
	mreqn.imr_address.s_addr = INADDR_ANY;
	address.s_addr = INADDR_ANY;
	mreqn.imr_ifindex = 0;

	test_sockopt_value_ext("IP_MULTICAST_IF set to INADDR_ANY mreqn",
				IP_MULTICAST_IF, &mreqn, sizeof(mreqn), &address, size);

	mreqn.imr_address.s_addr = inet_addr("127.0.0.1");
	address.s_addr = inet_addr("127.0.0.1");
	test_sockopt_value_ext("IP_MULTICAST_IF set to 127.0.0.1 mreqn",
				IP_MULTICAST_IF, &mreqn, sizeof(mreqn), &address, size);


	/* Errors */
	test_setsockopt_error("IP_MULTICAST_IF bad optlen",
				IP_MULTICAST_IF, &address, 3, EINVAL);

	address.s_addr = inet_addr("238.0.10.0");
	test_setsockopt_error("IP_MULTICAST_IF address 238.0.10.0",
					IP_MULTICAST_IF, &address,
					sizeof(address), EADDRNOTAVAIL);
}

int main()
{
	initialize();

	test_if();

	report_and_exit();
	return 0;
}
