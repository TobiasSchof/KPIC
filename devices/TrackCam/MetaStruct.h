/*
 * This file is an image structure loosely based on the MILK group's but for
 *    specific use with the KPIC NSFIU CRED2 tracking camera.
 *
 * Images created and written to by this structure are compatible with the 
 *    shmlib python class for shared memory on nfiuserver.
 *
 * This structure is meant to be used on nfiuserver (CentOS), so portability 
 *    is not considered.
 */

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
 * Defines a structure to hold the image's metadata
 */ 
typedef struct
{

    // image name
    char name[80] = "";

    // the time this memory was created
    struct timespec crtime;

    // the last time this memory was accessed
    struct timespec latime;

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

    //  keeps track of the last updated slice in the buffer
    uint8_t cnt1 = 0;

    // keeps track of how many semaphores this structure has
    //    (Note: this is only semaphores to track new data, not locks)
    uint8_t semNb = 0;

} im_metadata;

/*
 * gives the size of a datatype as encoded by im_metadata
 *
 * Inputs:
 *    size = where the size will be stored (in bytes)
 *    enc = the encoding of the type
 * Outputs:
 *    int = 0 if method is successful, -1 if encoding not found
 */
int get_size(size_t* size, int enc){
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
