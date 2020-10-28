/*
 * A header file that contains definitions for the shared memory class. It is
 *   meant to mimic the shared memory python library on nfiuserver.
 */

#include <exception>
#include <time.h>
#include <semaphore.h>
#include <stdint.h>
#include <string>

// the directory where semaphores are stored
#define SEM_DIR "/dev/shm"

/*
 * Defines a complex number with float precision
 */
typedef struct{
    float re;
    float im;
} complex_float;

/*
 * Defines a complex number with double precision
 */
typedef struct{
    double re;
    double im;
} complex_double;

/*
 * an exception to be thrown when a shm that doesn't exist is attached to
 */
class MissingSharedMemory: public std::exception{
    
    virtual const char* what() const throw(){
        return "No shared memory, please create.";
    }
}; 

/*
 * Defines a structure to hold the image's metadata
 */ 
typedef struct
{

    // image name
    char name[80] = "";

    // the time this memory was created
    struct timespec crtime;

    // the time that the image was acquired from the frame grabber
    struct timespec atime;

    // keeps track of the number of times this image has been updated since
    //    creation
    uint64_t cnt0 = 0;

    // the number of elements (product of non-zero elements of size)
    uint32_t nel = 0;

    // size should have 3 elements, 0 if an axis doesn't exist
    uint16_t size[3] = {0,0,0};

    // 1, 2, and 3 axis images are supported
    uint8_t naxis = 0;

    /* the data type stored in the picture
     *    1:  uint8_t
     *    2:  int8_t
     *    3:  uint16_t
     *    4:  int16_t
     *    5:  uint32_t
     *    6:  int32_t
     *    7:  uint64_t
     *    8:  int64_t
     *    9:  IEEE 754 single-precision binary floating-point format: binary32
     *    10: IEEE 754 double-precision binary floating-point format: binary64
     *    11: complex_float
     *    12: complex_double
     */
    uint8_t dtype = 0;

    // keeps track of the last updated slice in the buffer
    uint8_t mmap = 1;

    // keeps track of whether this data is croppable
    uint8_t croppable = 0;

} im_metadata;

class Shm{

    public:
        // public methods

        /*
         * Constructor to open a shared memory
         *
         * Inputs:
         *   filepath = path to the shared memory file backing 
         *             Should be of the form '/tmp/dir/shmName.im.shm'
         */
        Shm(std::string filepath);

        /*
         * Constructor to create a shared memory
         *
         * Inputs:
         *   filepath = path where the shared memory backing should be stored
         *             Should be of the form '/tmp/dir/shmName.im.shm'
         *   size []  = dimensions of the data to be stored
         *             Should be one, two, or three dimensions
         *   dims     = the number of dimensions of the data.
         *             Should match the length of the size array
         *   dtype    = the type of data to be stored
         *             Should be an encoding defined by im_metadata
         *   data     = a pointer to the data meant to be used to create shm
         *   mmap     = whether this shm should be marked as one to mmap or 
         *             just to be read/written as a normal file 
         */
        Shm(std::string filepath, uint16_t size[], uint8_t dims, uint8_t dtype, 
            void *seed, bool do_mmap, bool croppable);

        // Loads all metadata
        void getMetaData();

        /* 
         * Loads and returns the cnt0 metadata element
         *
         * Returns:
         *   uint64_t = cnt0
         */
        uint64_t getCounter();

        /*
         * Sets the data in the shm.
         *   Note: a basic pointer is used for the data to make the method
         *         independant of dtype. The method may not check that data
         *         is valid, so ensure that the pointer points to an area of
         *         memory at least DATA_SIZE in size.
         *
         * Inputs:
         *   new_data = a pointer to the start of the data to be written.
         */
        void set_data(const void *new_data);

        /*
         * Gets the current data from the shm and returns a pointer to it.
         *
         * Inputs:
         *   loc  = a pointer to somewhere to store the data. The size of the
         *         area pointed to by loc should be AT LEAST DATA_SIZE
         *   wait = whether a semaphore should be waited on before fetching 
         */
        void get_data(void *loc, bool wait=false);

        /*
         * Updates size in the metadata, as well as the DATA_SIZE variable
         *
         * Inputs:
         *   size = how to resize this data
         */
        void resize(uint16_t dim1, uint16_t dim2, uint16_t dim3);

        // destructor
        ~Shm();

        // public parameters

        // metadata structure
        im_metadata mtdata;
        // the name of the semaphore belonging to this shm.
        // if this shm doesn't have a semaphore, this will be an empty string
        std::string sem_nm = "";
        // semaphore to add wait for updates
        sem_t *sem; 
        // size of entire data
        size_t DATA_SIZE;
        // shm file name
        std::string fname;

    private:
        // private methods

        // private parameters

        // lock to protect the shm
        sem_t *lock;
        // boolean to represent whether this shm already has a semaphore
        bool has_sem = false;
        /* file name beginning of a sempahore for this shm.
         *    if /tmp/dir/Module.im.shm is a shm, then the semaphore will be
         *    named /dirModule_semxx and will be saved in SEM_DIR as
         *    sem.dirModule_semxx where xx are integers.
         *    sem_fnm will be sem.dirModule_sem in this case
         */
        std::string sem_fnm;
        // mmap location
        char *buf;
        // offsets for quick access
        const uint8_t ATIME_OFFSET = sizeof(mtdata.name)+sizeof(mtdata.crtime);
        const uint8_t CNT0_OFFSET = ATIME_OFFSET + sizeof(mtdata.atime);
        const uint8_t NEL_OFFSET = CNT0_OFFSET + sizeof(mtdata.cnt0);
        const uint8_t DATA_OFFSET = sizeof(im_metadata);
        // size of a single piece of data
        size_t UNIT_SIZE;
};
