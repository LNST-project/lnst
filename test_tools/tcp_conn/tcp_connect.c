#include <stdio.h>
#include <unistd.h>
#include <string.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h>

#include <errno.h>
#include <signal.h>


int connection_handlers[1024];
int handlers_count;

int debug_on = 0;
int cont = 0;

int usage()
{
    printf("./tcp_connect -p [port_range] -a [ipaddr]\n");
    return 0;
}

#define MSG_MAX 256
char msg[MSG_MAX];

int debug(char* msg)
{
    if (debug_on)
    {
        printf("Debug: %s\n", msg);
    }
}

void terminate_connections(int p)
{
    int cc;

    debug("signalled");
    for (cc=0; cc < handlers_count; cc++)
    {
        snprintf(msg, MSG_MAX, "killing process %i", connection_handlers[cc]);
        debug(msg);
        kill(connection_handlers[cc], SIGKILL);
    }
}

int handle_connections(char* host, int port)
{
    int conn_sock;
    int remote_sock;
    struct sockaddr_in my_addr;
    struct sockaddr remote;
    int end_loop = 0;
    char data[] = "abcdefghijklmnopqrstuvwxyz0123456789";
    char buf[21*10*strlen(data)+1];

    snprintf(msg, MSG_MAX, "Starting connection on %s port %i", host, port);
    debug(msg);

    my_addr.sin_family = AF_INET;
    my_addr.sin_port = htons(port);
    if (inet_aton(host, &(my_addr.sin_addr)) == 0)
    {
        printf("failed on inet_aton()\n");
        return 1;
    }

    do
    {
        conn_sock = socket(AF_INET, SOCK_STREAM, 0);
        if (conn_sock == -1)
        {
            perror("fail on socket()");
            return 1;
        }

        if (connect(conn_sock, (struct sockaddr*) &my_addr, sizeof(struct sockaddr_in)) == -1)
        {
            perror("fail on connect");
            return 1;
        }

        int bursts = 5*(random() % 10) + 1;
        int b;
        int sum = 0;

        for (b=0; b < bursts; b++)
        {
            int parts = 20*(random() % 10) + 1;
            int j;

            sum += parts*strlen(data);
            for (j = 0; j < parts; j++)
            {
                strncpy(buf + (j*strlen(data)), data, strlen(data));
            }

            int wr_rc = write(conn_sock, buf, parts * strlen(data));
            usleep(100*(random()%100));
        }

        snprintf(msg, MSG_MAX, "sent %i bytes (bursts: %i)", sum, bursts);
        debug(msg);
        snprintf(msg, MSG_MAX, "closing connection on port %i", port);
        debug(msg);

        close(conn_sock);
    } while (cont);

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

    memset(&sa, 0, sizeof(sa));

    sa.sa_handler = &terminate_connections;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    handlers_count = 0;

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
            break;
        }
    }

    if (strlen(host_str) == 0)
    {
        usage();
        return 1;
    }

    /* spawn process to handle every port specified */
    for (p = start_port; p < end_port; p++){
        if ((rc = fork()) > 0)
        {
            /* parent, add pid to the list */
            connection_handlers[handlers_count++] = rc;
        }
        else if (rc == 0)
        {
            /* child */
            sa.sa_handler = SIG_DFL;
            sigaction(SIGTERM, &sa, NULL);
            sigaction(SIGINT, &sa, NULL);
            handle_connections(host_str, p);
            return 0;
        }
    }

    /* gather children */
    int child_status;
    int i;
    for (i=0; i < handlers_count; i++)
    {
        wait(&child_status);
        debug("worker finished");
    }

    debug("tcp_connect finished");

    return 0;
}
