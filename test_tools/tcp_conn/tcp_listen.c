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

int listener_count;
int listeners[1024];
int *connection_count;

int debug_on = 0;
int cont = 0;
int *term_flag;

sem_t *mutex;

int usage()
{
    printf("./tcp_listen -p [port_range] -a [ipaddr]\n");
    return 0;
}

void debug(char* msg)
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
    debug("signal received, killing servers");
    *term_flag = 1;
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

    int on = 1;
    if (setsockopt(listen_sock, SOL_SOCKET, SO_REUSEADDR, (const char*) &on, sizeof(on)) == -1)
    {
        perror("fail on setsockopt");
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

        sem_wait(mutex);
        *connection_count += 1;
        sem_post(mutex);


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
    } while (cont && (*term_flag) == 0);

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
    int shm;

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
    memset(&sa2, 0, sizeof(sa2));

    sa.sa_handler = &terminate_connections;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);

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
        while (wait(&child_status) == -1  && errno == EINTR)
        {
            ;
        }
        debug("worker finished");
    }

    debug("tcp_listener finished");

    printf("handled %i connections\n", *connection_count);

    return 0;
}
