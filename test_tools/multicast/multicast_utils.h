/*
 * multicast_utils.h - common tools for kernel multicast tests
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

#ifndef __MULTICAST_UTILS_H__
#define __MULTICAST_UTILS_H__

#include <stdio.h>
#include <string.h>
#include <errno.h>

#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <sys/select.h>

#include <signal.h>
#include <time.h>

#include <stdlib.h>
#include <unistd.h>

#if !defined(SEND) && !defined(RECEIVE)
#error  "At least one of SEND/RECEIVE macros must be defined!"
#endif

#include "parameters.h"

#define MESSAGE "Hello world!"

int __verbosity = 0;

/* Verbose print */
#define printv(args...) \
	if (__verbosity > 0) \
	{ \
		printf(args); \
		fflush(stdout); \
	}

/** Initiailze socket for receiving multicast data */
int init_in_socket(struct in_addr multiaddr, short port)
{
	int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
	if (sockfd < 0)	{
		perror("socket()");
		exit(EXIT_FAILURE);
	}

	struct sockaddr_in addr;
	addr.sin_family = AF_INET;
	addr.sin_port = htons(port);
	addr.sin_addr = multiaddr;
	memset(&(addr.sin_zero), 0, sizeof(addr.sin_zero));

	if (bind(sockfd, (struct sockaddr*) &addr, sizeof(addr)) < 0) {
		perror("bind()");
		exit(EXIT_FAILURE);
	}

	return sockfd;
}

/** Initialize socket for sending multicast data */
int init_out_socket()
{
	int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
	if (sockfd < 0) {
		perror("socket()");
		exit(EXIT_FAILURE);
	}

	return sockfd;
}

/** Close a socket */
void free_socket(int sockfd)
{
	close(sockfd);
}

/** Wait for data up to `duration' seconds */
int wait_for_data(int sockfd, int duration, int packet_limit)
{
	const char message[] = MESSAGE;
	char buffer[] = MESSAGE;
	memset(buffer, 0, sizeof(buffer));

	int num_received = 0;

	fd_set receive_fd_set;
	struct timeval timeout;

	time_t deadline = time(NULL) + duration;

	printv("Receiving\n");

	while (1) {
		FD_ZERO(&receive_fd_set);
		FD_SET(sockfd, &receive_fd_set);

		if (duration == 0) {
			timeout.tv_sec  = 5;
			timeout.tv_usec = 0;
		} else {
			time_t now = time(NULL);
			if ((deadline - now) <= 0)
				break;

			timeout.tv_sec  = deadline - now;
			timeout.tv_usec = 0;
		}


		if (select(sockfd + 1, &receive_fd_set,	NULL, NULL, &timeout) > 0) {
			recv(sockfd, buffer, sizeof(buffer), 0);
			if (strncmp(message, buffer, sizeof(buffer)) == 0) {
				num_received++;

				printv(".");
				if (!(num_received % 10))
					printv("\n");

				if (packet_limit > 0 && num_received > packet_limit)
					break;
			}
		}
	}

	printv("\n");

	return num_received;
}

/** Send data for specified amount of time */
int send_data(int sockfd, struct in_addr multiaddr, short port,
					int duration, double delay)
{
	const char message[] = MESSAGE;
	int i = 0;

	struct sockaddr_in addr;

	addr.sin_family = AF_INET;
	addr.sin_addr = multiaddr;
	addr.sin_port = htons(port);
	memset(&(addr.sin_zero), 0, sizeof(addr.sin_zero));

	struct timespec delay_value;
	delay_value.tv_sec = 0;
	delay_value.tv_nsec = delay * 999999999;

	printv("Sending...\n");

	time_t started_at = time(NULL);
	while (duration == 0 || (time(NULL) - started_at) < duration) {
		i++;
		sendto(sockfd, message, strlen(message), 0,
			(struct sockaddr*) &addr, sizeof(addr));

		printv(".");
		if (!(i % 10))
			printv("\n");

		nanosleep(&delay_value, NULL);
	}

	printv("\n");

	return i;
}

#endif
