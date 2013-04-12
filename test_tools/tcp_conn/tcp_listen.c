#include <stdio.h>
#include <unistd.h>
#include <string.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h>

#include <errno.h>
#include <signal.h>

int listener_count;
int listeners[1024];

int connection_count;
int debug_on = 0;
int cont = 0;

int usage()
{
    printf("./tcp_listen -p [port_range] -a [ipaddr]\n");
    return 0;
}

int debug(char* msg)
{
    if (debug_on)
    {
        printf("Debug: %s\n", msg);
    }
}

#define MSG_MAX 256
char msg[MSG_MAX];

void terminate_connections(int p)
{
    int l;

    debug("signal received, killing servers");
    for (l=0; l < listener_count; l++)
    {
        snprintf(msg, MSG_MAX, "killing process %i", listeners[l]);
        debug(msg);
        kill(listeners[l], SIGKILL);
    }
}

void connection_counter(int p)
{
    debug("increase counter");
    connection_count += 1;
}

int handle_connections(char* host, int port)
{
    int listen_sock;
    struct sockaddr_in my_addr;
    socklen_t my_addr_size = sizeof(my_addr);
    int remote_sock;
    struct sockaddr_in remote;
    socklen_t remote_size = sizeof(remote);
    char data[256];

    snprintf(msg, MSG_MAX, "Starting listener on %s port %i", host, port);
    debug(msg);

    bzero(&my_addr, my_addr_size);
    my_addr.sin_family = AF_INET;
    my_addr.sin_port = htons(port);
    if (inet_aton(host, &(my_addr.sin_addr)) == 0)
    {
        printf("failed on inet_aton()\n");
        return 1;
    }

    if ((listen_sock = socket(AF_INET, SOCK_STREAM, 0)) == -1)
    {
        perror("fail on socket creation");
        return 1;
    }

    if (bind(listen_sock, (struct sockaddr*) &my_addr, sizeof(struct sockaddr_in)))
    {
        perror("fail on bind");
        return 1;
    }

    if (listen(listen_sock, 0))
    {
        perror("fail on listen");
        return 1;
    }

    do
    {
        struct in_addr ra = remote.sin_addr;
        char host_address_str[256];
        ssize_t read_rc;

        /* handle single connection */
        bzero(&remote, remote_size);
        remote_sock = accept(listen_sock, (struct sockaddr*) &remote, &remote_size);
        if (remote_sock == -1)
        {
            perror("failure on accept");
            close(listen_sock);
            return 1;
        }

        inet_ntop(AF_INET, &ra, host_address_str, 255);
        snprintf(msg, MSG_MAX, "accepted connection from host %s port %i", host_address_str, port);
        debug(msg);

        int sum = 0;
        while (read_rc = read(remote_sock, &data, 256))
        {
            sum += read_rc;
        }

        snprintf(msg, MSG_MAX, "connection closed, read %d bytes (%i)", sum, port);
        debug(msg);
        close(remote_sock);
        kill(getppid(), SIGUSR1);
    } while (cont);

    close(listen_sock);

    return 0;
}

int main(int argc, char **argv)
{
    int rc;
    int p;
    char port_str[256];
    char str_port_start[128];
    char str_port_end[128];
    char host_str[16] = "\0";
    int start_port;
    int end_port;
    int opt;
    char *delimiter;
    struct sigaction sa;
    struct sigaction sa2;

    sa.sa_handler = &terminate_connections;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    sa2.sa_handler = &connection_counter;
    sigaction(SIGUSR1, &sa2, NULL);

    /* collect program args */
    while ((opt = getopt(argc, argv, "p:a:dc")) != -1) {
        switch (opt) {
        case 'p':
            strncpy(port_str, optarg, 256);
            port_str[256-1]='\0';
            delimiter = strchr(port_str, '-');
            if (delimiter == NULL)
            {
                usage();
            }
            strncpy(str_port_start, port_str, delimiter - port_str);
            str_port_start[delimiter - port_str] = '\0';
            strncpy(str_port_end, delimiter+1, strlen(port_str) - (delimiter+1-port_str));
            start_port = atoi(str_port_start);
            end_port = atoi(str_port_end);
            break;
        case 'a':
            strncpy(host_str, optarg, 64);
            host_str[16-1] = '\0';
            break;
        case 'd':
            debug_on = 1;
            break;
        case 'c':
            cont = 1;
        }
    }

    if (strlen(host_str) == 0)
    {
        usage();
        return 1;
    }

    listener_count = 0;
    /* spawn process to handle every port specified */
    for (p = start_port; p < end_port; p++){
        if ((rc = fork()) > 0)
        {
            /* parent, add pid to the list */
            listeners[listener_count++] = rc;
        }
        else if (rc == 0)
        {
            /* child */
            sa.sa_handler = SIG_DFL;
            sigaction(SIGTERM, &sa, NULL);
            sigaction(SIGINT, &sa, NULL);

            /* run the main processing loop */
            handle_connections(host_str, p);
            return 0;
        }
    }

    /* gather children */
    int child_status;
    int i;
    for (i=0; i < listener_count; i++)
    {
        int rc = -1;
        while (wait(&child_status) == -1  && errno == EINTR)
        {
            ;
        }
        debug("worker finished");
    }

    debug("tcp_listener finished");

    printf("handled %i connections\n", connection_count);

    return 0;
}
