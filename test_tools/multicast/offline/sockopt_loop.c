/*
 * sockopt_loop.c - IP_MULTICAST_LOOP socket option test
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


void test_loop()
{
	int value;
	size_t size = sizeof(value);

	value = 1;
	test_getsockopt("IP_MULTICAST_LOOP default value",
				IP_MULTICAST_LOOP, &value, size);

	value = 0;
	test_sockopt_value("IP_MULTICAST_LOOP set to zero",
				IP_MULTICAST_LOOP, &value, size);

	/* Errors */
	test_setsockopt_error("IP_MULTICAST_LOOP bad optlen",
				IP_MULTICAST_LOOP, &value, 0, EINVAL);
}

int main()
{
	initialize();

	test_loop();

	report_and_exit();
	return 0;
}
