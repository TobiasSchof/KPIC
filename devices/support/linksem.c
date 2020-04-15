/*
 * A scripts that links a semaphore to another. It will wait on the first 
 *    semaphore and incrememnt the second one when done waiting. This is meant
 *    to be used as a subscription service so the second semaphore will not
 *    be incremented if it's value is already greater than 0.
 *
 * This script is meant to be persistent so semaphores are not cleaned up 
 *    (semaphores are supposed to be closed on process termination by OS)
 */

#include <stdio.h>
#include <fcntl.h>
#include <semaphore.h>

int main(int argc, char *argv[]){
    if (argc != 3){
        printf("Invalid parameters. E.G: linksem /name1 /name2\n");
        return 1;
    }

    sem_t *src = sem_open(argv[1], O_CREAT, 0644, 0);
    sem_t *dest = sem_open(argv[2], O_CREAT, 0644, 0);

    // an infinite loop to watch src semaphore and update dest accordingly
    while (argc == 3){
        sem_wait(src);
        int val;
        sem_getvalue(dest, &val);
        if (val < 1){ sem_post(dest); }
    }

    return 0;
}
