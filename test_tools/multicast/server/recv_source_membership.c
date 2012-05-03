/*
 * recv_drop_membership.c - Join multicast group only for a specific
 *                          source and then leave it in the middle of
 *                          ongoing communication
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
	struct ip_mreq_source mreq;
	mreq.imr_multiaddr  = params.multiaddr;
	mreq.imr_interface  = params.interface;
	mreq.imr_sourceaddr = params.sourceaddr;

	if (setsockopt(sockfd, IPPROTO_IP, IP_ADD_SOURCE_MEMBERSHIP,
				   &(mreq), sizeof(mreq)) < 0)
	{
		perror("setsockopt");
		return -1;
	}

	num_recv = wait_for_data(sockfd, params.duration/2, 0);
	printf("packets_received=%d\n", num_recv);

	if (setsockopt(sockfd, IPPROTO_IP, IP_DROP_SOURCE_MEMBERSHIP,
				   &(mreq), sizeof(mreq)) < 0)
	{
		perror("setsockopt");
		return -1;
	}

	num_recv = wait_for_data(sockfd, params.duration/2, 0);
	printf("packets_received_after_drop=%d\n", num_recv);

	return EXIT_SUCCESS;
}
