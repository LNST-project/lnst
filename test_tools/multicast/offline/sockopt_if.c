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

	inet_pton(AF_INET, "127.0.0.1", &address);
	test_sockopt_value("IP_MULTICAST_IF set to 127.0.0.1",
				IP_MULTICAST_IF, &address, size);

	struct ip_mreqn mreqn;
	mreqn.imr_multiaddr.s_addr = 0xdeadbeef;
	mreqn.imr_address.s_addr = INADDR_ANY;
	mreqn.imr_ifindex = 0;

	test_sockopt_value("IP_MULTICAST_IF set to INADDR_ANY",
				IP_MULTICAST_IF, &mreqn, sizeof(mreqn));

	mreqn.imr_address.s_addr = 0x0100007f;
	test_sockopt_value("IP_MULTICAST_IF set to 127.0.0.1",
				IP_MULTICAST_IF, &mreqn, sizeof(mreqn));


	/* Errors */
	test_setsockopt_error("IP_MULTICAST_IF bad optlen",
				IP_MULTICAST_IF, &address, 3, EINVAL);

	inet_pton(AF_INET, "238.0.10.0", &address);
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
