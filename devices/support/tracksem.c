/*
 * This script is meant to track a master semaphore and update individual
 *    new data semaphores.
 *
 * The name of the semaphore should be provided. This script assumes that the
 *    name to track is of the form '/(dir)(shm name)_MASTER' and will increment
 *    any semaphores of the name '/(dir)(shm name)_sem(xxx)' when the master
 *    semaphore is updated
 */

#include <stdio.h>
#include <fcntl.h>
#include <semaphore.h>
#include <dirent.h>
#include <string.h>
#include <stdlib.h>

int main(int argc, char *argv[]){

    if (argc != 2){
        printf("Invalid parameters. E.G: tracksem /TrackCamIMG_MASTER_SEM\n");
        return 1;
    }

    // connect to the master semaphore
    sem_t *master = sem_open(argv[1], O_CREAT, 0644, 0);

    // set up template name for semaphores
    size_t pref_len = strlen(argv[1]);
    char *pref = malloc(pref_len);
    if (pref == NULL){
        printf("Malloc failed.\n");
        return 1;
    }
    // register the free call for pref to be used at exit
    void free_me(){ free(pref); }
    atexit(free_me);

    // we remove the 7 characters '/', 'MASTER_SEM' and append 'sem.', 'sem'
    sprintf(pref, "sem.%.*ssem", (int)(strlen(argv[1])-11), argv[1]+1);

    while (argc == 2){
        sem_wait(master);

        DIR *dr = opendir("/dev/shm");

        if (dr == NULL){
            printf("Semaphore directory not found.");
            return 1;
        }

        struct dirent *de;

        // check which sems are alive
        while ((de = readdir(dr)) != NULL){
            // check whether this is a TrackCam semaphore
            if (strncmp(pref, de->d_name, pref_len) == 0){
                // get semaphore name from file name
                size_t nm_len = strlen(de->d_name) - 3;
                char *sem_nm = (char*) malloc(nm_len);
                if (sem_nm == NULL) {
                    printf("Semaphore directory not found.");
                    return 1;
                }
                sprintf(sem_nm, "/%.*s", nm_len, de->d_name+4);

                // connect to semaphore
                sem_t *sem = sem_open(sem_nm, O_CREAT, 0644, 0);

                // increment then close the semaphore
                sem_post(sem);
                sem_close(sem);

                // free the memory used for the name
                free(sem_nm);                
            }
        }
    }

    return 0;
}
