/*
 * This class implements the shared memory class defined in shmlib.hpp
 */

#include <semaphore.h>  // adds POSIX semaphores
#include <fcntl.h>      // adds O POSIX tags (O_CREAT)
#include <thread>       // adds threading
#include <sys/mman.h>   // adds mmap
#include <sys/stat.h>   // adds mmap tags
#include <sys/types.h>   // with stat, adds directory checking
#include <time.h>       // adds timespec and enables getting the time
#include <string>       // adds string
#include <cstring>      // adds strcpy
#include <fstream>      // adds file reading/writing
#include <stdint.h>     // adds uxxx_t types
#include <dirent.h>     // adds directory inspection
#include <string>       // adds string parsing

#include "KPIC_shmlib.hpp"

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
 *    int = -1 if SEM_DIR isn't found, else 0
 */
int postSems(std::string sem_fnm){
    DIR *dir;
    struct dirent *ent;
    if ((dir = opendir(SEM_DIR)) != NULL) {
        /* print all the files and directories within directory */
        while ((ent = readdir(dir)) != NULL) {
            if (strncmp(sem_fnm.c_str(), ent->d_name, sem_fnm.length()) == 0){
                // replace 'sem.' in file name with '/' to get semaphore name
                std::string sem_nm = ent->d_name;
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
        closedir (dir);

        return 0;
    } else {
        // could not open directory
        return -1;
    }
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
 * an exception to be thrown when a shm can't be read because dtype is invalid
 */
class CorruptSharedMemory: public std::exception{

    virtual const char* what() const throw(){
        return "Dtype not recognized.";
    }
} CorruptShm;

Shm::Shm(std::string filepath, bool has_sem)
{
    fname = filepath;

    // open file
    FILE* backing = fopen(fname.c_str(), "rb+");
    // check that file was opened successfully
    if (!backing) { throw MissingSharedMemory(); }
    // read in metadata
    fread(&mtdata, sizeof(mtdata), 1, backing);
    // close file
    fclose(backing);

    if (get_size(&UNIT_SIZE, mtdata.dtype) == -1) { throw CorruptShm; } 
    DATA_SIZE = UNIT_SIZE*mtdata.nel;

    std::string sempref = fname;
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

    lock = sem_open((sempref + "_lock").c_str(), O_CREAT, 0644, 1);
    if (lock == SEM_FAILED){
        perror("lock opening failed.");
        exit(EXIT_FAILURE);
    }
    // remove starting '/' from sempref and add prepend 'sem.' and append '_sem'
    sem_fnm = sempref + "_sem";
    sem_fnm.erase(0, 1);
    sem_fnm = "sem." + sem_fnm;

    // mmap or set buffer pointer to null
    if (mtdata.mmap == 1){
        // open file as read and write to mmap
        backing = fopen(fname.c_str(), "rb+");
        // open the shm
        buf = (char*) mmap(0, DATA_SIZE, PROT_READ | PROT_WRITE, 
            MAP_SHARED, fileno(backing), 0); 
        if (buf == MAP_FAILED){ perror("mmap"); exit(EXIT_FAILURE); }
        // close file
        fclose(backing);
    } else { buf = NULL; }

    if (has_sem) { get_sem(); }
}

Shm::Shm(std::string filepath, uint16_t size[], uint8_t dims, uint8_t dtype, 
        void *seed, bool do_mmap, bool has_sem, bool croppable)
{
    fname = filepath;

    // set data type and data size
    mtdata.dtype = dtype;
    if (get_size(&UNIT_SIZE, mtdata.dtype) == -1) { throw CorruptShm; } 

    std::string sempref = fname;
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
    // remove extension
    sempref.erase(sempref.find("."), sempref.length());

    lock = sem_open((sempref + "_lock").c_str(), O_CREAT, 0644, 1);
    if (lock == SEM_FAILED){
        perror("lock opening failed.");
        exit(EXIT_FAILURE);
    }
    sem_fnm = sempref + "_sem";
    sem_fnm.erase(0, 1);
    sem_fnm = "sem." + sem_fnm;

    // set times in metadata
    timespec_get(&mtdata.crtime, TIME_UTC);
    mtdata.atime = mtdata.crtime;

    // set name in metadata based on filename
    sempref.erase(0, 1);
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

    // set mmap in metadata
    mtdata.mmap = (uint8_t) do_mmap;
    // set croppable in metadata
    mtdata.croppable = (uint8_t) croppable;
    
    // make any directories required
    int old = 0;
    int next = fname.find("/", old);
    struct stat info;
    std::string dir = "";
    while (next != std::string::npos){
        dir.append(fname.substr(old, next-old+1));
        if (stat(dir.c_str(), &info) != 0){ 
            mkdir(dir.c_str(), S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH); 
        }
        else if(!(info.st_mode & S_IFDIR)) { 
            perror("Cannot make directory tree. Would overwrite a file."); 
            exit(EXIT_FAILURE);
        }
        old = next+1;
        next = fname.find("/", old);
    }

    // open file
    FILE* backing = fopen(fname.c_str(), "wb+");
    // write in metadata
    fwrite(&mtdata, sizeof(mtdata), 1, backing);
    // write in data
    fwrite(seed, UNIT_SIZE, mtdata.nel, backing);

    // mmap if desired
    if (mmap){
        fseek(backing, 0, SEEK_SET);
        // create mmap
        buf = (char*) mmap(0, DATA_SIZE, PROT_READ | PROT_WRITE, 
            MAP_SHARED, fileno(backing), 0); 
    } else { buf = NULL; }

    // close file
    fclose(backing);

    // connect to a semaphore if one was requested
    if (has_sem){ get_sem(); }

    // start a thread to post semaphores
    std::thread post(postSems, sem_fnm);
    
    post.detach();
}

void Shm::getMetaData(){
    if (buf) {
        memcpy(&mtdata, buf, sizeof(mtdata)); 
    } else {
        // open file as read only to check existence
        FILE* backing = fopen(fname.c_str(), "rb");
        // check for file existence
        if (!backing){ throw MissingSharedMemory(); } 
        // read in metadata
        fread(&mtdata, DATA_OFFSET, 1, backing); 
        fclose(backing);
    }
}

uint64_t Shm::getCounter(){
    if (buf) {
        memcpy(&mtdata.cnt0, buf + CNT0_OFFSET, sizeof(mtdata.cnt0));
    } else {
        FILE* backing = fopen(fname.c_str(), "rb");
        if (!backing){ throw MissingSharedMemory(); } 
        // move to cnt0 position
        fseek(backing, CNT0_OFFSET, SEEK_SET);
        fread(&mtdata.cnt0, sizeof(mtdata.cnt0), 1, backing); 
        fclose(backing);
    }

    return mtdata.cnt0;
}

void Shm::set_data(const void *new_data){
    struct timespec time;
    timespec_get(&time, TIME_UTC);

    // update metadata
    mtdata.atime = time;
    mtdata.cnt0++;

    size_t edit = sizeof(mtdata.atime) + sizeof(mtdata.cnt0);

    // grab the lock
    sem_wait(lock);

    if (buf) {
        // copy the data to the shared memory
        memcpy(buf+DATA_OFFSET, new_data, DATA_SIZE);
        // copy new metadata to shm
        memcpy(buf+ATIME_OFFSET, &mtdata.atime, edit);
    } else {
        FILE* backing = fopen(fname.c_str(), "rb+");
        if (!backing){ throw MissingSharedMemory(); }
        // write atime
        fseek(backing, ATIME_OFFSET, SEEK_SET);
        fwrite(&mtdata.atime, edit, 1, backing);
        // write data
        fseek(backing, DATA_OFFSET, SEEK_SET);
        fwrite(new_data, DATA_SIZE, 1, backing);
        // close file
        fclose(backing);
    }
    // release the lock
    sem_post(lock);

    // start a thread to post semaphores
    std::thread post(postSems, sem_fnm);
    
    post.detach();
}

void Shm::get_data(void *loc, bool wait){
    if (wait){
        
        // get a semaphore if we need one
        if (!has_sem) { get_sem(); }

        // otherwise wait on our semaphore
        sem_wait(sem); 
    }

    // grab lock
    sem_wait(lock);

    if (buf) {
        // copy the data from the mmapping
        memcpy(loc, buf+DATA_OFFSET, DATA_SIZE);
        // get latest counter
        getCounter();
    } else {
        FILE* backing = fopen(fname.c_str(), "rb");
        if (!backing){ throw MissingSharedMemory(); }
        // get CNT0 (we avoid using getCounter() to only open file once)
        fseek(backing, CNT0_OFFSET, SEEK_SET);
        fread(&mtdata.cnt0, sizeof(mtdata.cnt0), 1, backing);
        // get the data
        fseek(backing, DATA_OFFSET, SEEK_SET);
        fread(loc, DATA_SIZE, 1, backing);
        // close the file
        fclose(backing);
    }
    //release lock
    sem_post(lock);
}

void Shm::resize(uint16_t dim1, uint16_t dim2, uint16_t dim3){

    mtdata.size[0] = dim1;
    mtdata.size[1] = dim2;
    mtdata.size[2] = dim3;

    mtdata.nel = 1;
    for (int i=0; i<3; i++){
        if (mtdata.size[i] > 0){ mtdata.nel *= mtdata.size[i]; }
    }

    DATA_SIZE = mtdata.nel * UNIT_SIZE;

    size_t len = sizeof(mtdata.nel)+sizeof(mtdata.size);
    if (buf){
        memcpy(buf+NEL_OFFSET, &mtdata.nel, len);
    } else {
        FILE* backing = fopen(fname.c_str(), "rb+");
        if(!backing){ throw MissingSharedMemory(); }
        // update nel and size at once
        fseek(backing, NEL_OFFSET, SEEK_SET);
        fwrite(&mtdata.nel, len, 1, backing);
        // close the file
        fclose(backing);
    }
}

void Shm::get_sem(){
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

}

Shm::~Shm(){
    // if this shm has a semaphore, unlink and close it
    if (has_sem) { 
        sem_unlink(sem_nm.c_str());
        sem_close(sem);
    }
    // close lock
    sem_close(lock);
}
