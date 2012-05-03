/*
 * send_igmp_query.c - igmp querier simulator
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

#include "igmp_utils.h"

void general_query(int sockfd, struct in_addr saddr)
{
	int len = sizeof(struct iphdr) + sizeof(struct ipopts)
				+ sizeof(struct igmphdr);

	unsigned char *buffer = malloc(len);
	if (buffer == NULL) {
		perror("malloc()");
		exit(EXIT_FAILURE);
	}

	struct iphdr *ip_header = (struct iphdr *) buffer;

	struct ipopts *ip_options = (struct ipopts *)(buffer + sizeof(struct iphdr));

	struct igmphdr *igmp_header;
	igmp_header = (struct igmphdr *) (buffer + sizeof(struct iphdr)
						+ sizeof(struct ipopts));

	struct in_addr daddr;
	inet_aton("224.0.0.1", &daddr);
	ip_header_init(ip_header, saddr, daddr);
	ip_options_init(ip_options);

	igmp_header->type = IGMP_HOST_MEMBERSHIP_QUERY;
	igmp_header->code = 0;

	/* IGMPv1 general query */
	igmp_header->group = 0;

	igmp_header->csum = 0;
	igmp_header->csum = checksum((unsigned short *) igmp_header,
					sizeof(struct igmphdr));
	send_ip_frame(sockfd, daddr, buffer, len);
	free(buffer);
}

void group_specific_query(int sockfd, struct in_addr saddr,
			struct in_addr daddr,struct in_addr group,
			int max_resp_time)
{
	int len = sizeof(struct iphdr) + sizeof(struct ipopts)
				+ sizeof(struct igmphdr);

	unsigned char *buffer = malloc(len);
	if (buffer == NULL) {
		perror("malloc()");
		exit(EXIT_FAILURE);
	}

	struct iphdr *ip_header = (struct iphdr *) buffer;

	struct ipopts *ip_options = (struct ipopts *)(buffer + sizeof(struct iphdr));

	struct igmphdr *igmp_header;
	igmp_header = (struct igmphdr *) (buffer + sizeof(struct iphdr)
						+ sizeof(struct ipopts));

	ip_header_init(ip_header, saddr, daddr);
	ip_options_init(ip_options);

	igmp_header->type = IGMP_HOST_MEMBERSHIP_QUERY;
	igmp_header->code = max_resp_time;

	igmp_header->group = group.s_addr;

	igmp_header->csum = 0;
	igmp_header->csum = checksum((unsigned short *) igmp_header,
					sizeof(struct igmphdr));

	send_ip_frame(sockfd, daddr, buffer, len);
	free(buffer);
}

void group_and_source_specific_query(int sockfd, struct in_addr saddr,
			struct in_addr daddr, struct in_addr group,
			struct in_addr *sources, int num_sources,
			int max_resp_time)
{
	int len = sizeof(struct iphdr) + sizeof(struct ipopts)
		+ sizeof(struct igmpv3_query) + num_sources*sizeof(__be32);

	unsigned char *buffer = malloc(len);
	if (buffer == NULL) {
		perror("malloc()");
		exit(EXIT_FAILURE);
	}

	struct iphdr *ip_header = (struct iphdr *) buffer;

	struct ipopts *ip_options = (struct ipopts *)(buffer + sizeof(struct iphdr));

	struct igmpv3_query *igmp_header;
	igmp_header = (struct igmpv3_query *) (buffer + sizeof(struct iphdr)
							+ sizeof(struct ipopts));

	ip_header_init(ip_header, saddr, daddr);
	ip_options_init(ip_options);

	igmp_header->type = IGMP_HOST_MEMBERSHIP_QUERY;
	igmp_header->code = max_resp_time;

	igmp_header->group = group.s_addr;

	int i;
	for (i = 0; i < num_sources; i++)
		igmp_header->srcs[i] = sources[i].s_addr;

	igmp_header->csum = 0;
	igmp_header->csum = checksum((unsigned short *) igmp_header,
					sizeof(struct igmpv3_query) +
					num_sources*sizeof(__be32));

	send_ip_frame(sockfd, daddr, buffer, len);
	free(buffer);
}

int main(int argc, char** argv)
{
	struct parameters params;
	parse_args(argc, argv, &params);

	int sockfd = init_raw_socket(params.interface);

	switch(params.query_type) {
		case IGMP_GENERAL_QUERY:
			general_query(sockfd, params.interface);
			break;
		case IGMP_GROUP_SPECIFIC_QUERY:
			group_specific_query(sockfd, params.interface,
					params.destaddr, params.multiaddr,
					params.max_resp_time);
			break;
		case IGMP_GROUP_AND_SOURCE_SPECIFIC_QUERY:
			group_and_source_specific_query(sockfd,params.interface,
					params.destaddr, params.multiaddr,
					&params.sourceaddr, 1,
					params.max_resp_time);

			break;
	}

	return EXIT_SUCCESS;
}
