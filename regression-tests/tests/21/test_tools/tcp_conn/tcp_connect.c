#include <stdio.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <sys/wait.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <arpa/inet.h>

#include <errno.h>
#include <signal.h>
#include <semaphore.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>

#define IPCKEY 5678

int connection_handlers[1024];
int handlers_count;
int *connection_count;

int debug_on = 0;
int cont = 0;
int *term_flag;

sem_t *mutex;

int usage()
{
    printf("./tcp_connect -p [port_range] -a [ipaddr] [-d] [-c] [-6]\n");
    return 0;
}

#define MSG_MAX 256
char msg[MSG_MAX];

void debug(char* msg)
{
    if (debug_on)
    {
        printf("Debug: %s\n", msg);
    }
}

void terminate_connections(int p)
{
    debug("signalled");
    *term_flag = 1;
}

int handle_connections(char* host, int port, int ipv6)
{
    int conn_sock;
    struct sockaddr_in my_addr;
    struct sockaddr_in6 my_addr6;
    char data[] = "abcdefghijklmnopqrstuvwxyz0123456789";
    char buf[21*10*strlen(data)+1];
    int family;

    snprintf(msg, MSG_MAX, "Starting connection on %s port %i", host, port);
    debug(msg);

    if (ipv6)
    {
        family = my_addr6.sin6_family = AF_INET6;
        my_addr6.sin6_port = htons(port);
        if (inet_pton(AF_INET6, host, &my_addr6.sin6_addr) != 1) {
            perror("fail on inet_pton");
            return 1;
        }
    }
    else
    {
        family = my_addr.sin_family = AF_INET;
        my_addr.sin_port = htons(port);
        if (inet_aton(host, &(my_addr.sin_addr)) == 0)
        {
            printf("failed on inet_aton()\n");
            return 1;
        }
    }

    do
    {
        conn_sock = socket(family, SOCK_STREAM, 0);
        if (conn_sock == -1)
        {
            perror("fail on socket()");
            return 1;
        }

        struct sockaddr* sa;
        socklen_t sa_len;
        if (ipv6)
        {
            sa = (struct sockaddr*) &my_addr6;
            sa_len = sizeof(struct sockaddr_in6);
        }
        else
        {
            sa = (struct sockaddr*) &my_addr;
            sa_len = sizeof(struct sockaddr_in);
        }

        if (connect(conn_sock, sa, sa_len) == -1)
        {
            perror("fail on connect");
            return 1;
        }

        sem_wait(mutex);
        *connection_count += 1;
        sem_post(mutex);

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

            if (write(conn_sock, buf, parts * strlen(data)) == -1)
            {
                perror("failed to send data");
                return 1;
            }
            usleep(100*(random()%100));
        }

        snprintf(msg, MSG_MAX, "sent %i bytes (bursts: %i)", sum, bursts);
        debug(msg);
        snprintf(msg, MSG_MAX, "closing connection on port %i", port);
        debug(msg);

        close(conn_sock);
    } while (cont && (*term_flag) == 0);

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
    int shm;
    int ipv6 = 0;

    term_flag = mmap(NULL, sizeof *term_flag, PROT_READ | PROT_WRITE,
                    MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    *term_flag = 0;

    connection_count = mmap(NULL, sizeof *connection_count, PROT_READ | PROT_WRITE,
                    MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    *connection_count = 0;

    /* counter synchronization stuff - semaphore and shared memory */
    if ((shm = shm_open("myshm", O_RDWR | O_CREAT, S_IRWXU))  < 0) {
        perror("shm_open");
        exit(1);
    }

    if ( ftruncate(shm, sizeof(sem_t)) < 0 ) {
        perror("ftruncate");
        exit(1);
    }

    /* place shared mutex into shared memory */
    if ((mutex = (sem_t*) mmap(NULL, sizeof(sem_t), PROT_READ | PROT_WRITE, MAP_SHARED, shm, 0)) == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }

    if( sem_init(mutex,1,1) < 0)
    {
        perror("semaphore initilization");
        exit(0);
    }

    /* signal handling */
    memset(&sa, 0, sizeof(sa));

    sa.sa_handler = &terminate_connections;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

    handlers_count = 0;

    /* collect program args */
    while ((opt = getopt(argc, argv, "p:a:dc6")) != -1) {
        switch (opt) {
        case 'p':
            strncpy(port_str, optarg, 256);
            port_str[256-1]='\0';
            delimiter = strchr(port_str, '-');
            if (delimiter == NULL)
            {
                usage();
                return 1;
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
        case '6':
            ipv6 = 1;
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
            handle_connections(host_str, p, ipv6);
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

    printf("made %i connections\n", *connection_count);

    return 0;
}
