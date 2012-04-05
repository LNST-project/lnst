CC=gcc
TOOLS_DIR=.
CFLAGS=-Wall -Wextra -I$(TOOLS_DIR)

SENDERS=send_simple
RECEIVERS=recv_simple
OFFLINE=sockopt_loop sockopt_ttl sockopt_if

all: $(SENDERS) $(RECEIVERS) $(OFFLINE)

$(SENDERS):
	$(CC) $(CFLAGS) -o $@ client/$@.c

$(RECEIVERS):
	$(CC) $(CFLAGS) -o $@ server/$@.c

$(OFFLINE):
	$(CC) $(CFLAGS) -o $@ offline/$@.c

clean:
	rm -f $(SENDERS) $(RECEIVERS) $(OFFLINE)
