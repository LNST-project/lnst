CC=gcc

all: tcp_listen tcp_connect

tcp_listen: tcp_listen.c
		$(CC) -o tcp_listen tcp_listen.c -pthread -lrt

tcp_connect: tcp_connect.c
		$(CC) -o tcp_connect tcp_connect.c -pthread -lrt

clean:
		rm -f tcp_connect tcp_listen
