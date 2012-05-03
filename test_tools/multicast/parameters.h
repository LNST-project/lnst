/*
 * parameters.h - common code for parsing sender/receiver parameters
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

#ifndef __PARAMETERS_H__
#define __PARAMETERS_H__

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

#ifdef IGMP
enum __igmp_query_types {
	IGMP_GENERAL_QUERY = 1,
	IGMP_GROUP_SPECIFIC_QUERY = 2,
	IGMP_GROUP_AND_SOURCE_SPECIFIC_QUERY = 3
};
#endif

/** Structure that carries test parameters */
struct parameters
{
	int duration; /* seconds */

	struct in_addr multiaddr;
	short port;
	struct in_addr interface;

#if defined(RECEIVE) || defined(IGMP)
	struct in_addr sourceaddr;
#endif

#ifdef SEND
	double delay;
	int ttl;
	int loop;
#endif

#ifdef IGMP
	short query_type;
	struct in_addr destaddr;
	int max_resp_time;
#endif
};

/** Initialize parameters struct with default values. */
void default_parameters(struct parameters* params)
{
	params->duration = 10;
	params->port = 0;
	memset(&params->multiaddr, 0, sizeof(struct in_addr));
	memset(&params->interface, 0, sizeof(struct in_addr));

#if defined(RECEIVE) || defined(IGMP)
	memset(&params->sourceaddr, 0, sizeof(struct in_addr));
#endif

#ifdef SEND
	params->delay = 0.1;
	params->ttl = 1;
	params->loop = 1;
#endif

#ifdef IGMP
	params->query_type = IGMP_GENERAL_QUERY;
	memset(&params->destaddr, 0, sizeof(struct in_addr));
	params->max_resp_time = 10;
#endif
}

void usage(char *program_name, int retval)
{
	printf("usage: %s\n", program_name);
	printf("       -h | --help                    print this\n");
	printf("       -i | --interface a.b.c.d       local interface to use for communication\n");
	printf("       -v | --verbose                 print additional information during the runtime\n");

	printf("\n");

	printf("       -d | --duration x              test duration\n");

#ifdef SEND
	printf("       -f | --delay x                 delay between messages\n");
#endif

	printf("\n");

	printf("       -a | --address a.b.c.d         multicast group address\n");

#if defined(SEND) || defined(IGMP)
	printf("       -s | --source_address a.b.c.d  source address\n");
#endif

#ifdef IGMP
	printf("       -z | --dest_address a.b.c.d    destination address\n");
#endif

#if defined(SEND) || defined(RECEIVE)
	printf("       -p | --port x                  port number\n");
#endif

	printf("\n");

#ifdef IGMP
	printf("       -q | --query_type              query type\n");
	printf("       -r | --max_resp_time x         maximum response time\n");
#endif

#ifdef SEND
	printf("       -t | --ttl x                   time to live for IP packet\n");
	printf("       -l | --loop x                  loopback multicast communication\n");
#endif

	exit(retval);
}

/** Generic function for parsing arguments */
void parse_args(int argc, char** argv, struct parameters* args)
{
#ifdef SEND
	#define __send_opts "f:t:l:p:"
#else
	#define __send_opts ""
#endif

#if defined(RECEIVE) || defined(IGMP)
	#define __recv_opts "s:p:"
#else
	#define __recv_opts ""
#endif

#ifdef IGMP
	#define __igmp_opts "q:z:r:"
#else
	#define __igmp_opts ""
#endif

#ifdef IGMP
	int dest_was_set = 0;
#endif

	static const char* opts = "d:a:i:v" __send_opts __recv_opts
					__igmp_opts;


	static struct option long_options[] =
	{
		{"help",                required_argument, NULL, 'h'},
		{"interface",           required_argument, NULL, 'i'},
		{"verbose",             no_argument,       NULL, 'v'},
		{"duration",            required_argument, NULL, 'd'},
		{"multicast_address",   required_argument, NULL, 'a'},

#if defined(RECEIVE) || defined(IGMP)
		{"source_address",      required_argument, NULL, 's'},
#endif

#ifdef SEND
		{"delay",               required_argument, NULL, 'f'},
		{"ttl",	                required_argument, NULL, 't'},
		{"loop",                required_argument, NULL, 'l'},
#endif

#if defined(SEND) || defined(RECEIVE)
		{"port",                required_argument, NULL, 'p'},
#endif

#ifdef IGMP
		{"query_type",          required_argument, NULL, 'q'},
		{"dest_address",        required_argument, NULL, 'z'},
		{"max_resp_time",       required_argument, NULL, 'r'},

#endif
		{0,                    0,                 NULL, 0}
	};

	default_parameters(args);

	int opt;
	int option_index = 0;
	while((opt = getopt_long(argc, argv, opts, long_options,
						&option_index)) != -1) {
		switch (opt) {
		case 'd':
			args->duration = atoi(optarg);
			break;
		case 'a':
			inet_pton(AF_INET, optarg, &(args->multiaddr));
			break;
		case 'p':
			args->port = atoi(optarg);
			break;
		case 'h':
			usage(argv[1], EXIT_SUCCESS);
			break;
		case 'i':
			inet_pton(AF_INET, optarg, &(args->interface));
			break;
		case 'v':
			__verbosity = 1;
			break;
#if defined(RECEIVE) || defined(IGMP)
		case 's':
			inet_pton(AF_INET, optarg, &(args->sourceaddr));
			break;
#endif

#ifdef SEND
		case 'f':
			args->delay = atof(optarg);
			break;
		case 't':
			args->ttl = atoi(optarg);
			break;
		case 'l':
			args->loop = atoi(optarg);
			break;
#endif

#ifdef IGMP
		case 'q':
			args->query_type = atoi(optarg);
			/*if (strcmp(optarg, "general") == 0) {
				args->query_type = IGMP_GENERAL_QUERY;
			} else if (strcmp(optarg, "group_specific") == 0) {
				args->query_type = IGMP_GROUP_SPECIFIC_QUERY;
			} else if (strcmp(optarg, "group_and_source_specific") == 0) {
				args->query_type = IGMP_GROUP_AND_SOURCE_SPECIFIC_QUERY;
			} else {
				fprintf(stderr, "%s: undefined query type\n",
								argv[0]);
				exit(EXIT_FAILURE);
			}*/
			break;
		case 'z':
			inet_pton(AF_INET, optarg, &(args->destaddr));
			dest_was_set = 1;
			break;
		case 'r':
			args->max_resp_time = atoi(optarg);
			break;
#endif
		default: /* '?' */
			fprintf(stderr, "%s: invalid test options\n", argv[0]);
			usage(argv[0], EXIT_FAILURE);
		}
	}

#ifdef IGMP
	if (!dest_was_set)
		args->destaddr = args->multiaddr;
#endif

}

#endif
