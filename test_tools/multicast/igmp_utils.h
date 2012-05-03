/*
 * igmp_utils.h - tools for sending/receiving IGMP packets
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

#ifndef __IGMP_UTILS_H__
#define __IGMP_UTILS_H__

#include <stdio.h>
#include <string.h>
#include <errno.h>

#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>

#include <signal.h>
#include <time.h>

#include <getopt.h>
#include <stdlib.h>
#include <unistd.h>

#include <netinet/ip.h>
#include <linux/igmp.h>

#define IGMP
#include "parameters.h"

int __verbosity = 0;

/* Verbose print */
#ifndef printv
#define printv(args...) \
	if (__verbosity > 0) \
	{ \
		printf(args); \
		fflush(stdout); \
	}
#endif

struct ipopt_ra {
	u_char type;
	u_char length;
	uint16_t data;
};

struct ipopts {
	struct ipopt_ra ra;
};

unsigned short checksum(unsigned short *addr, int len)
{
	register int nleft = len;
	register int sum = 0;
	u_short answer = 0;

	while (nleft > 1) {
		sum += *addr++;
		nleft -= 2;
	}


	if (nleft == 1) {
		*(u_char *)(&answer) = *(u_char *)addr;
		sum += answer;
	}


	sum = (sum >> 16) + (sum & 0xffff);
	sum += (sum >> 16);
	answer = ~sum;
	return(answer);
}

void ip_header_init(struct iphdr *iph, struct in_addr saddr,
				struct in_addr daddr)
{
	iph->version = 4;
	iph->ihl = 6;
	iph->tos = 0xc0;
	iph->id = htons(0);
	iph->frag_off = htons(0b0100000000000000); /* DF */
	iph->ttl = 1;
	iph->protocol = IPPROTO_IGMP;

	iph->saddr = saddr.s_addr;
	iph->daddr = daddr.s_addr;
}

void ip_options_init(struct ipopts *options)
{
	options->ra.type = 0x94;
	options->ra.length = 4;
	options->ra.data = 0;
}

void send_ip_frame(int sockfd, struct in_addr daddr,
			unsigned char* buffer, size_t len)
{
	struct sockaddr_in servaddr;
	bzero(&servaddr, sizeof(struct sockaddr_in));
	servaddr.sin_family = AF_INET;
	servaddr.sin_addr = daddr;

	int bytes_sent = sendto(sockfd, buffer, len, 0, (struct sockaddr *)&servaddr,
				sizeof(struct sockaddr_in));
	if (bytes_sent < 0) {
		perror("sendto()");
		exit(EXIT_FAILURE);
	}

	FILE *fp;
	fp=fopen("deeebg", "wb");
	fwrite(buffer, sizeof(char), len, fp);
}

int init_raw_socket(struct in_addr interface)
{
	int sockfd = socket(AF_INET, SOCK_RAW, IPPROTO_RAW);
	if (sockfd < 0)	{
		perror("socket()");
		exit(EXIT_FAILURE);
	}

	struct sockaddr_in addr;
	bzero(&addr, sizeof(struct sockaddr_in));
	addr.sin_family = AF_INET;
	addr.sin_addr = interface;

	int result = bind(sockfd, (struct sockaddr *)&addr,
				sizeof(struct sockaddr_in));

	if (result < 0) {
		perror("bind()");
		exit(EXIT_FAILURE);
	}

	return sockfd;
}

/** Close a socket */
void free_socket(int sockfd)
{
	close(sockfd);
}


#endif
