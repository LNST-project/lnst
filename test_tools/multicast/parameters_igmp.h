/*
 * parameters_igmp.h - common code for parsing sender/receiver parameters
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

#ifndef __PARAMETERS_IGMP_H__
#define __PARAMETERS_IGMP_H__

#include <stdio.h>
#include <string.h>
#include <errno.h>

#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>

#include <signal.h>
#include <time.h>

#include <getopt.h>
#include <stdlib.h>
#include <unistd.h>

extern int __verbosity;

enum __igmp_query_types {
	IGMP_GENERAL_QUERY = 1,
	IGMP_GROUP_SPECIFIC_QUERY = 2,
	IGMP_GROUP_AND_SOURCE_SPECIFIC_QUERY = 3
};

/** Structure that carries test parameters */
struct parameters
{
	struct in_addr multiaddr;
	struct in_addr interface;

	short query_type;
	struct in_addr sourceaddr;
	struct in_addr destaddr;
	int max_resp_time;
};

/** Initialize parameters struct with default values. */
void default_parameters(struct parameters* params)
{
	memset(&params->multiaddr, 0, sizeof(struct in_addr));
	memset(&params->interface, 0, sizeof(struct in_addr));

	params->query_type = IGMP_GENERAL_QUERY;
	memset(&params->sourceaddr, 0, sizeof(struct in_addr));
	memset(&params->destaddr, 0, sizeof(struct in_addr));
	params->max_resp_time = 0;
}

void usage(char *program_name, int retval)
{
	printf("usage: %s\n", program_name);
	printf("       -h | --help                        print this\n");
	printf("       -v | --verbose                     print additional information during the runtime\n");
	printf("       -i | --interface a.b.c.d           local interface to use for communication\n");

	printf("\n");

	printf("       -a | --multicast_address a.b.c.d   multicast group address (v2 and v3 only)\n");
	printf("       -s | --source_address a.b.c.d      multicast source (v3 only)\n");
	printf("       -d | --dest_address a.b.c.d        destination address of the IP packet\n");

	printf("\n");

	printf("       -q | --query_type                  query type [1,2,3]\n");
	printf("       -r | --max_resp_time x             maximum response time\n");
	exit(retval);
}

/** Generic function for parsing arguments */
void parse_args(int argc, char** argv, struct parameters* args)
{
	int dest_was_set = 0;

	static const char* opts = "i:a:q:s:d:r:hv";
	static struct option long_options[] =
	{
		{"interface",           required_argument, NULL, 'i'},
		{"multicast_address",   required_argument, NULL, 'a'},
		{"query_type",          required_argument, NULL, 'q'},
		{"source_address",      required_argument, NULL, 's'},
		{"dest_address",        required_argument, NULL, 'd'},
		{"max_resp_time",       required_argument, NULL, 'r'},
		{"help",                no_argument,       NULL, 'h'},
		{"verbose",             no_argument,       NULL, 'v'},
		{0,                     0,                 NULL, 0}
	};

	default_parameters(args);

	int opt;
	int option_index = 0;
	while((opt = getopt_long(argc, argv, opts, long_options,
						&option_index)) != -1) {
		switch (opt) {
		case 'i':
			inet_pton(AF_INET, optarg, &(args->interface));
			break;
		case 'a':
			inet_pton(AF_INET, optarg, &(args->multiaddr));
			break;
		case 'q':
			args->query_type = atoi(optarg);
			break;
		case 's':
			inet_pton(AF_INET, optarg, &(args->sourceaddr));
			break;
		case 'd':
			inet_pton(AF_INET, optarg, &(args->destaddr));
			dest_was_set = 1;
			break;
		case 'r':
			args->max_resp_time = atoi(optarg);
			break;
		case 'h':
			usage(argv[0], EXIT_SUCCESS);
			break;
		case 'v':
			__verbosity = 1;
			break;
		default: /* '?' */
			fprintf(stderr, "%s: invalid options\n", argv[0]);
			usage(argv[0], EXIT_FAILURE);
		}
	}

	if (!dest_was_set)
		args->destaddr = args->multiaddr;
}

#endif
