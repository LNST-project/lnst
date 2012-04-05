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

/** Structure that carries test parameters */
struct parameters
{
	int duration; /* seconds */

	struct in_addr multiaddr;
	short port;
	struct in_addr interface;

#ifdef RECEIVE
	struct in_addr sourceaddr;
#endif

#ifdef SEND
	double delay;
	int ttl;
	int loop;
#endif
};

/** Initialize parameters struct with default values. */
void default_parameters(struct parameters* params)
{
	params->duration = 10;
	params->port = 0;
	memset(&params->multiaddr, 0, sizeof(struct in_addr));
	memset(&params->interface, 0, sizeof(struct in_addr));
#ifdef RECEIVE
	memset(&params->sourceaddr, 0, sizeof(struct in_addr));
#endif

#ifdef SEND
	params->delay = 0.1;
	params->ttl = 1;
	params->loop = 1;
#endif
}

/** Generic function for parsing arguments */
void parse_args(int argc, char** argv, struct parameters* args)
{
#ifdef SEND
	static const char* opts = "d:a:p:i:f:l:t:v";
#endif

#ifdef RECEIVE
	static const char* opts = "d:a:p:s:i:v";
#endif

	static struct option long_options[] =
	{
		{"duration",          required_argument, NULL, 'd'},
		{"multicast_address", required_argument, NULL, 'a'},
		{"port",              required_argument, NULL, 'p'},
		{"interface",         required_argument, NULL, 'i'},
		{"verbose",           no_argument,       NULL, 'v'},
#ifdef RECEIVE
		{"source_address",    required_argument, NULL, 's'},
#endif

#ifdef SEND
		{"delay",             required_argument, NULL, 'f'},
		{"ttl",	              required_argument, NULL, 't'},
		{"loop",              required_argument, NULL, 'l'},
#endif
		{0,                   0,                 NULL, 0}
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
		case 'i':
			inet_pton(AF_INET, optarg, &(args->interface));
			break;
		case 'v':
			__verbosity = 1;
			break;
#ifdef RECEIVE
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
		default: /* '?' */
			printf("%s: invalid test options\n", argv[0]);
			exit(EXIT_FAILURE);
		}
	}
}
