CC=gcc
TOOLS_DIR=.
CFLAGS=-Wall -Wextra -I$(TOOLS_DIR)

SENDERS=send_simple
RECEIVERS=recv_simple recv_membership recv_source_membership recv_block_source
OFFLINE=sockopt_loop sockopt_ttl sockopt_if sockopt_membership sockopt_source_membership sockopt_block_source max_groups

all: $(SENDERS) $(RECEIVERS) $(OFFLINE)

$(SENDERS):
	$(CC) $(CFLAGS) -o $@ client/$@.c

$(RECEIVERS):
	$(CC) $(CFLAGS) -o $@ server/$@.c

$(OFFLINE):
	$(CC) $(CFLAGS) -o $@ offline/$@.c

clean:
	rm -f $(SENDERS) $(RECEIVERS) $(OFFLINE)
