/*
 * sockopt_block_source.c - IP_BLOCK/UNBLOCK_SOURCE socket option test
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


void test_block_source()
{
	struct ip_mreq_source mreq;

	mreq.imr_multiaddr.s_addr = inet_addr("127.0.0.1");
	mreq.imr_interface.s_addr = inet_addr("127.0.0.1");
	mreq.imr_sourceaddr.s_addr = inet_addr("192.168.0.1");
	test_setsockopt_error("IP_BLOCK_SOURCE Bad multicast address",
			IP_BLOCK_SOURCE, &mreq, sizeof(mreq), EINVAL);

	mreq.imr_multiaddr.s_addr = inet_addr("239.1.2.3");
	mreq.imr_interface.s_addr = inet_addr("255.255.255.255");
	mreq.imr_sourceaddr.s_addr = inet_addr("192.168.0.1");
	test_setsockopt_error("IP_BLOCK_SOURCE Bad interface",
			IP_BLOCK_SOURCE, &mreq, sizeof(mreq), ENODEV);

	test_setsockopt_error("IP_BLOCK_SOURCE Bad optlen",
			IP_BLOCK_SOURCE, &mreq, 2, EINVAL);
}

void test_unblock_source()
{
	struct ip_mreq_source mreq;

	mreq.imr_multiaddr.s_addr = inet_addr("127.0.0.1");
	mreq.imr_interface.s_addr = inet_addr("127.0.0.1");
	mreq.imr_sourceaddr.s_addr = inet_addr("192.168.0.1");
	test_setsockopt_error("IP_UNBLOCK_SOURCE Bad multicast address",
			IP_UNBLOCK_SOURCE, &mreq, sizeof(mreq), EINVAL);

	mreq.imr_multiaddr.s_addr = inet_addr("239.1.2.3");
	mreq.imr_interface.s_addr = inet_addr("127.0.0.1");
	mreq.imr_sourceaddr.s_addr = inet_addr("192.168.0.1");
	test_setsockopt_error("IP_UNBLOCK_SOURCE Not a member",
			IP_UNBLOCK_SOURCE, &mreq, sizeof(mreq), EINVAL);

	mreq.imr_multiaddr.s_addr = inet_addr("239.1.2.3");
	mreq.imr_interface.s_addr = inet_addr("255.255.255.255");
	mreq.imr_sourceaddr.s_addr = inet_addr("192.168.0.1");
	test_setsockopt_error("IP_UNBLOCK_SOURCE No device found",
			IP_UNBLOCK_SOURCE, &mreq, sizeof(mreq), ENODEV);

	test_setsockopt_error("IP_UNBLOCK_SOURCE Bad optlen",
			IP_UNBLOCK_SOURCE, &mreq, 5, EINVAL);
}

int main()
{
	initialize();

	test_block_source();
	test_unblock_source();

	report_and_exit();
	return 0;
}
