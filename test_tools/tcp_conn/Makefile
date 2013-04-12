CC=gcc

all: tcp_listen tcp_connect

tcp_listen: tcp_listen.c
		$(CC) -o tcp_listen tcp_listen.c

tcp_connect: tcp_connect.c
		$(CC) -o tcp_connect tcp_connect.c

clean:
		rm -f tcp_connect tcp_listen
