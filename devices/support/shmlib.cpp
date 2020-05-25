/*
 * This class implements the shared memory class defined in shmlib.hpp
 */

#include <semaphore.h> // adds POSIX semaphores
#include <fcntl.h>     // adds O POSIX tags (O_CREAT)
#include <thread>      // adds threading
#include <sys/mman.h>  // adds mmap
#include <sys/stat.h>  // adds mmap tags
#include <time.h>      // adds timespec and enables getting the time
#include <string>      // adds string
#include <cstring>     // adds strcpy
#include <fstream>     // adds file reading/writing
#include <stdint.h>    // adds uxxx_t types
#include <dirent.h>    // adds directory inspection

#include <iostream>    // printing for debugging

#include "shmlib.hpp"

/*
 * Posts all alive semaphores. 
 *   (can be slow, meant to be used in a thread)
 *
 * The point of opening and closing semaphores for every post is to ensure that
 *   we update semaphores that were destroyed and recreated between posts.
 *   the cost of creating a semaphore, while not non-existant, shouldn't slow
 *   down things too much. But, this function is still best used in a thread.
 *
 * Inputs:
 *    sem_fnm = the file name for a semaphore
 * Returns:
 *    int = -1 if SEM_DIR isn't found or if directory can't be closed, else 0
 */
int postSems(std::string sem_fnm){
    // open the semaphore directory (from shmlib header)
    DIR *dr = opendir(SEM_DIR);

    if (dr == NULL){ return -1; }

    // dirent structure will reveal the files within the directory
    struct dirent *de;

    while ((de = readdir(dr)) != NULL){
        // check if this semaphore's name matches this shm's semaphores' names
        if (strncmp(sem_fnm.c_str(), de->d_name, sem_fnm.length()) == 0){
            // replace 'sem.' in file name with '/' to get semaphore name
            std::string sem_nm(de->d_name);
            sem_nm.erase(0, 4);
            sem_nm = "/" + sem_nm;

            // open the semaphore
            sem_t *sem = sem_open(sem_nm.c_str(), O_CREAT, 0644, 0);   

            // increment the semaphore
            sem_post(sem);

            // close the semaphore
            sem_close(sem);
        } 
    }
    return closedir(dr);
}

int get_size(size_t* size, int enc)
{
    switch (enc) {

    case 1: *size = sizeof(uint8_t);
            return 0; 
    case 2: *size = sizeof(int8_t);
            return 0; 
    case 3: *size = sizeof(uint16_t);
            return 0; 
    case 4: *size = sizeof(int16_t);
            return 0; 
    case 5: *size = sizeof(uint32_t);
            return 0; 
    case 6: *size = sizeof(int32_t);
            return 0; 
    case 7: *size = sizeof(uint64_t);
            return 0; 
    case 8: *size = sizeof(int64_t);
            return 0; 
    case 9: *size = sizeof(float);
            return 0; 
    case 10: *size = sizeof(double);
            return 0; 
    case 11: *size = sizeof(complex_float);
            return 0; 
    case 12: *size = sizeof(complex_double);
            return 0; 
    default: return -1;
    
    }
}

/*
 * an exception to be thrown when a shm that doesn't exist is attached to
 */
class MissingSharedMemory: public std::exception{
    
    virtual const char* what() const throw(){
        return "No shared memory, please create.";
    }
} NoShm; 

/*
 * an exception to be thrown when a shm can't be read because dtype is invalid
 */
class CorruptSharedMemory: public std::exception{

    virtual const char* what() const throw(){
        return "Dtype not recognized.";
    }
} CorruptShm;

Shm::Shm(std::string filepath)
{
    // open file as read only to check existence
    FILE* backing = fopen(filepath.c_str(), "r");

    // check for file existence
    if (!backing){ throw NoShm; } 

    // read in metadata
    fread(&mtdata, DATA_OFFSET, 1, backing); 

    fclose(backing);

    if (get_size(&UNIT_SIZE, mtdata.dtype) == -1) { throw CorruptShm; } 
    DATA_SIZE = UNIT_SIZE*mtdata.nel;

    std::string sempref = filepath;
    // remove root-level directory
    size_t cut = sempref.find("/", 1);
    if (cut != std::string::npos) { 
        sempref = sempref.substr(cut, sempref.length());
    }
    // remove any other '/'
    while ((cut = sempref.find("/")) != std::string::npos){ 
        sempref.erase(cut, 1); 
    }
    // add '/' to beginning
    sempref = "/" + sempref;
    // remove '.im.shm'
    sempref.erase(sempref.find("."), sempref.length());

    lock = sem_open((sempref + "_lock").c_str(), O_CREAT, 0644, 0);
    // remove starting '/' from sempref and add prepend 'sem.' and append '_sem'
    sem_fnm = sempref + "_sem";
    sem_fnm.erase(0, 1);
    sem_fnm = "sem." + sem_fnm;

    // open file as read and write to mmap
    backing = fopen(filepath.c_str(), "a+");
    // open the shm
    buf = (char*) mmap(0, DATA_SIZE, PROT_READ | PROT_WRITE, 
        MAP_SHARED, fileno(backing), 0); 
    if (buf == MAP_FAILED){ perror("mmap"); exit(EXIT_FAILURE); }
    // close file
    fclose(backing);

    // copy data in the shm
    data = calloc(mtdata.nel, UNIT_SIZE);

    memcpy(data, buf + DATA_OFFSET, DATA_SIZE);
}

Shm::Shm(std::string filepath, uint16_t size[], uint8_t dims, uint8_t dtype, 
        char *seed)
{
    // set data type and data size
    mtdata.dtype = dtype;
    if (get_size(&UNIT_SIZE, mtdata.dtype) == -1) { throw CorruptShm; } 

    std::string sempref = filepath;
    // remove root-level directory
    size_t cut = sempref.find("/", 1);
    if (cut != std::string::npos) { 
        sempref = sempref.substr(cut, sempref.length());
    }
    // remove any other '/'
    while ((cut = sempref.find("/")) != std::string::npos){ 
        sempref.erase(cut, 1); 
    }
    // add '/' to beginning
    sempref = "/" + sempref;
    // remove '.im.shm'
    sempref.erase(sempref.find("."), sempref.length());

    lock = sem_open((sempref + "_lock").c_str(), O_CREAT, 0644, 0);
    sem_fnm = sempref + "_sem";

    // set times in metadata
    timespec_get(&mtdata.crtime, TIME_UTC);
    mtdata.latime = mtdata.crtime;
    mtdata.atime = mtdata.crtime;

    // set name in metadata based on filename
    strcpy(mtdata.name, sempref.c_str());

    // set nel, naxis, and size in metadata from size parameter
    for (int i=0; i < 3; i++){ mtdata.size[i] = 0; }
    mtdata.naxis = 0;
    mtdata.nel = 1;
    for (int i=0; i < dims; i++){
        if (size[i] > 0) {
            mtdata.naxis++;
            mtdata.nel *= size[i];
            mtdata.size[i] = size[i];
        } else { mtdata.size[i] = 0; }
    }

    DATA_SIZE = UNIT_SIZE*mtdata.nel;

    // create file backing
    FILE* backing = fopen(filepath.c_str(), "a+");

    // copy in metadata
    fwrite(&mtdata, sizeof(mtdata), 1, backing);

    // copy in data
    data = calloc(mtdata.nel, UNIT_SIZE);
    memcpy(data, seed, DATA_SIZE);

    // write data to file
    fwrite(data, UNIT_SIZE, mtdata.nel, backing); 

    // open shm
    buf = (char*) mmap(0, DATA_SIZE, PROT_READ | PROT_WRITE, 
        MAP_SHARED, fileno(backing), 0); 

    // close file
    fclose(backing);
}

void Shm::getMetaData(){
    memcpy(&mtdata, buf, sizeof(mtdata)); 
}

uint64_t Shm::getCounter(){
    memcpy(&mtdata.cnt0, buf + CNT0_OFFSET, sizeof(mtdata.cnt0));

    return mtdata.cnt0;
}

void Shm::setData(void *new_data){
    struct timespec time;
    timespec_get(&time, TIME_UTC);

    size_t edit = sizeof(mtdata.latime) + sizeof(mtdata.atime) + 
        sizeof(mtdata.cnt0);

    // copy the data to out local data
    memcpy(data, new_data, DATA_SIZE);
    
    // grab the lock
    sem_wait(lock);

    // copy the data to the shared memory
    memcpy(buf+DATA_OFFSET, data, DATA_SIZE);

    // update metadata
    mtdata.atime = time;
    timespec_get(&mtdata.latime, TIME_UTC);
    mtdata.cnt0++;

    // copy new metadata to shm
    memcpy(buf+LATIME_OFFSET, &mtdata.latime, edit);

    // release the lock
    sem_post(lock);

    // updatd cnt0
    getCounter();

    // start a thread to post semaphores
    std::thread post(postSems, sem_fnm);

    post.detach();
}

void* Shm::getData(){
    // grab lock
    sem_wait(lock);

    // copy the data from the mmapping
    memcpy(data, buf+DATA_OFFSET, DATA_SIZE);
    // update latime
    timespec_get(&mtdata.latime, TIME_UTC);
    // updated latime in shm
    memcpy(buf+LATIME_OFFSET, &mtdata.latime, sizeof(mtdata.latime));

    //release lock
    sem_post(lock);

    // return a pointer to the copy
    return data;
}

void* Shm::getData(bool wait){
    if (wait){
        // connect to an unused semaphore if we don't already have one
        if (!has_sem){
            // iterate through valid names until we find one not taken
            std::string sem_pref = sem_fnm;
            sem_pref.erase(0, 4);
            sem_pref = "/"+sem_pref;
            for (int i=0; i < 100; i++){
                if (i < 10){
                    sem = sem_open((sem_pref + "0" + std::to_string(i)).c_str(), 
                                    O_CREAT | O_EXCL, 0644, 0);
                } else {
                    sem = sem_open((sem_pref + std::to_string(i)).c_str(), 
                                    O_CREAT | O_EXCL, 0644, 0);
                }
                // the semaphore was free
                if (sem != SEM_FAILED){ 
                    has_sem = true; 
                    sem_nm = sem_pref;
                    if (i < 10) { sem_nm += "0"; }
                    sem_nm += std::to_string(i);
                    break; 
                }
            } 
        }
        // this means there were no available semaphores
        if (!has_sem) { perror("No available semaphore."); exit(EXIT_FAILURE); }

        // otherwise wait on our semaphore
        sem_wait(sem); 
    }
    // grab lock
    sem_wait(lock);

    // copy the data from the mmapping
    memcpy(data, buf+DATA_OFFSET, DATA_SIZE);
    // update latime
    timespec_get(&mtdata.latime, TIME_UTC);
    // updated latime in shm
    memcpy(buf+LATIME_OFFSET, &mtdata.latime, sizeof(mtdata.latime));

    //release lock
    sem_post(lock);

    // return a pointer to the copy
    return data;
}

Shm::~Shm(){
    // free memory calloced for data
    free(data);
    // if this shm has a semaphore, unlink and close it
    if (has_sem) { 
        sem_unlink(sem_nm.c_str());
        sem_close(sem);
    }
    // close lock
    sem_close(lock);
}
