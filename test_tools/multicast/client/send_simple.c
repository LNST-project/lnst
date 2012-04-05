/*
 * send_simple.c - simple sender setup for multicast tests
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

#define SEND
#include "multicast_utils.h"

int main(int argc, char** argv)
{
	struct parameters params;
	parse_args(argc, argv, &params);

	int sockfd = init_out_socket(&params);

	/* Sockopts setup */
	if (setsockopt(sockfd, IPPROTO_IP, IP_MULTICAST_LOOP,
			&(params.loop), sizeof(params.loop)) < 0) {
		perror("setsockopt");
		return EXIT_FAILURE;
	}

	if (setsockopt(sockfd, IPPROTO_IP, IP_MULTICAST_TTL,
			&(params.ttl), sizeof(params.ttl)) < 0) {
		perror("setsockopt");
		return EXIT_FAILURE;
	}

	if (setsockopt(sockfd, IPPROTO_IP, IP_MULTICAST_IF,
			&(params.interface), sizeof(params.interface)) < 0) {
		perror("setsockopt");
		return EXIT_FAILURE;
	}

	int num_sent = 0;
	num_sent = send_data(sockfd, params.multiaddr, params.port,
					params.duration, params.delay);

	printf("packets_sent=%d\n", num_sent);

	return EXIT_SUCCESS;
}
