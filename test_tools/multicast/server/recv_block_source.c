/*
 * recv_block_source.c - Join multicast group and then block and
 *                       unblock specific sources
 *
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

#define RECEIVE
#include "multicast_utils.h"

int main(int argc, char** argv)
{
	struct parameters params;
	parse_args(argc, argv, &params);

	int sockfd = init_in_socket(params.multiaddr, params.port);

	int num_recv = 0;
	struct ip_mreq mreq;
	mreq.imr_multiaddr  = params.multiaddr;
	mreq.imr_interface  = params.interface;

	struct ip_mreq_source mreqs;
	mreqs.imr_multiaddr  = params.multiaddr;
	mreqs.imr_interface  = params.interface;
	mreqs.imr_sourceaddr = params.sourceaddr;

	if (setsockopt(sockfd, IPPROTO_IP, IP_ADD_MEMBERSHIP,
				   &(mreq), sizeof(mreq)) < 0)
	{
		perror("setsockopt");
		return -1;
	}

	num_recv = wait_for_data(sockfd, params.duration/3, 0);
	printf("packets_received=%d\n", num_recv);

	if (setsockopt(sockfd, IPPROTO_IP, IP_BLOCK_SOURCE,
				   &(mreqs), sizeof(mreqs)) < 0)
	{
		perror("setsockopt");
		return -1;
	}

	num_recv = wait_for_data(sockfd, params.duration/3, 0);
	printf("packets_received_while_blocking=%d\n", num_recv);

	if (setsockopt(sockfd, IPPROTO_IP, IP_UNBLOCK_SOURCE,
				   &(mreqs), sizeof(mreqs)) < 0)
	{
		perror("setsockopt");
		return -1;
	}

	num_recv = wait_for_data(sockfd, params.duration/3, 0);
	printf("packets_received=%d\n", num_recv);

	return EXIT_SUCCESS;
}
