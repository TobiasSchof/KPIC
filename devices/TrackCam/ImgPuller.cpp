/*
 * This is a C++ script to update the tracking camera shared memory as a new
 *    image becomes available.
 * 
 * It Combines the First Light Imaging SDK with the shared memory structure
 *    used on KPIC.
 * 
 * Note: C++ is used so we can take advantage of the IRawImageReceivedObserver
 *    class in the C++ FLI SDK.
 *
 * TODO: Currently, a simple mutex lock is used to regulate resource access.
 *   This is done because the speeds seem to imply that nothing more is needed.
 *   If a speed up is desired, however, this can be changed to a more complex
 *   system which allows multiple readers to access the resource at once, while
 *   writer access locks the resource from any other readers/writers. 
 *
 *
 * Compiling:
 *    To compile use: 
 *       g++ ImgPuller.cpp -lpthread -L$FLISDK_DIR/lib/release -lFliSdk -I/$FLISDK_DIR/include
 *    May require a "sudo yum install libpng12.x86_64"
 */

// Note, since this system may be handled by someone more familiar with python
//   than c/c++, I've tried to comment more extensively

#include <semaphore.h>   // adds POSIX semaphores
#include <fcntl.h>       // adds O tags (O_CREAT)
#include <sys/stat.h>    // adds POSIX mode constants
#include <time.h>        // for getting the current time for timestamps
#include <sys/mman.h>    // for mmap
#include <sstream>       // for stringstream (to name semaphores)
#include <cstring>       // for strcpy
#include <fstream>       // for file reading/writing

#include "FliSdk.h"      // compile with $FLISDK_DIR/include
#include "MetaStruct.h"  // a custom structure to store metadata

// define directories for easier creating/access
#define SHM_DIR  "/tmp/TrackCam/"

// store offsets in metadata for easier access
// THESE NEED TO BE CHANGED IF IM_METADATA IS CHANGED
#define IMAGE_OFFSET   sizeof(im_metadata)
// writing to the shared memory assumes that latime, atime, and cnt0 are all
// continguous and that nel and size are the next two addresses
#define LATIME_OFFSET  96

// define constants for camera
#define MAX_PIX 327680 // this is 640X512 resolution

// a structure that defines a shared memory
typedef struct{
    im_metadata mtdata; // metadata
    char *shm;          // the mmap
    sem_t *lock;        // the lock for editing the mmap
    sem_t *sem;         // semaphore to keep track of new data
} shm;

/*
 * This is a class from the FLI SDK. Using it, we can create something that
 *    listens for when a new image is available.
 */
class ImageReceiver : public IRawImageReceivedObserver{

  public:
    // constructor
    ImageReceiver();
    // this is the method that handles when an image comes in
    virtual void imageReceived(const uint8_t* image);
    // this method lets the FG know when to update us
    virtual uint16_t fpsTrigger();

  // our private variables
  private:
    FliSdk *_fli;                 // the handler of the FG and camera
    shm img, ndr, exposure, temp; // state shms
    
};

/*
 * Every C/C++ script has a main method. This is what is actually run when
 *    a compiled script is ran.
 */
int main(){

    // instantiate our class, which handles everything else.
    ImageReceiver* handler = new ImageReceiver();

}

/*
 * This method will open a shared memory based on the integer passed
 *
 * Inputs:
 *   which = 0 = img, 1 = ndr, 2 = exposure, 3 = temp
 */
void shm_Open(shm *cur_shm, const char *filename, const char *shmname, 
    uint32_t nel, uint16_t size[3], uint8_t naxis, uint8_t dtype){

    // make the shm for the image
    // First we check if there is already a shm set up
    FILE* backing = fopen(SHM_DIR + *filename, "r");
    if (backing){ // This is the case where a shm exists, so read it
        // we need write/read access for mmap, so reopen file
        fclose(backing);
        backing = fopen(SHM_DIR + *filename, "wb+");
        // mmap the file
        cur_shm->shm = (char*) mmap(0, IMAGE_OFFSET+MAX_PIX, 
            PROT_READ | PROT_WRITE, MAP_SHARED, fileno(backing), 0);
        // load in the metadata
        fread(&cur_shm->mtdata, IMAGE_OFFSET, 1, backing);
        // mmap creates a copy of the file so we can close our copy now.
        fclose(backing);
    } else { // This is the case where no shm exists, so make it
        // we will need to reopen the file in write mode. So close it for now
        fclose(backing);

        struct timespec time;
        timespec_get(&time, TIME_UTC);
        // here we need to create the metadata
        strcpy(cur_shm->mtdata.name, shmname);
        cur_shm->mtdata.nel = nel;
        cur_shm->mtdata.size[0] = size[0];
        cur_shm->mtdata.size[2] = size[1];
        cur_shm->mtdata.size[3] = size[3];
        cur_shm->mtdata.naxis = naxis;
        cur_shm->mtdata.dtype = dtype;
        cur_shm->mtdata.crtime = time;
        cur_shm->mtdata.latime = time;
        cur_shm->mtdata.atime = time;

        // now we create the file and write in this info
        backing = fopen(SHM_DIR + *filename, "wb+");
        fwrite(&cur_shm->mtdata, sizeof(im_metadata), 1, backing);
        // now we create a place-holder for the data
        switch (dtype){
            case 1: 
                if (nel > 1) { 
                    uint8_t tmp[nel];
                    fwrite(&tmp, nel, 1, backing); 
                } else { 
                    uint8_t tmp = 0;
                    fwrite(&tmp, 1, 1, backing); }
            case 10: 
                double tmp = -5000.0;
                fwrite(&tmp, sizeof(tmp), 1, backing);
        }
        
        // now we can open the mmap
        cur_shm->shm = (char*) mmap(0, IMAGE_OFFSET+MAX_PIX, PROT_READ | PROT_WRITE,
            MAP_SHARED, fileno(backing), 0);

        // mmap creates a copy of the file so we can close our copy now.
        fclose(backing);
    }

    std::stringstream name;
    name << "/" << filename << "_lock";

    // the O_CREAT flag on POSIX semaphores will connect if the semaphore
    // already exists, and create it if it doesn't
    cur_shm->lock = sem_open(name.str().c_str(), O_CREAT, 0644, 1);

    // error checking
    if (cur_shm->lock == SEM_FAILED) { 
        std::cout << "Semaphore failure.\n"; exit(1); }

    name.str(""); name.clear();
    name << "/" << filename << "_MASTER_SEM";

    cur_shm->sem = sem_open(name.str().c_str(), O_CREAT, 0644, 0);

    // error checking
    if (cur_shm->sem == SEM_FAILED) { 
        std::cout << "Semaphore failure.\n"; exit(1); }

}

/*
 * Here we define our classes' constructor, which includes setup.
 */
ImageReceiver::ImageReceiver(){

    // instantiate a new FG/camera handler
    _fli = new FliSdk();

    // get all the available grabbers
    std::vector<std::string> listOfGrabbers = _fli->detectGrabbers();

    // if there are no grabbers
    if(!listOfGrabbers.size()){
        std::cout << "No grabbers detected. Check connection.";
        exit(1);
    }

    // connect to first grabber in the list
    // NOTE: this script needs to be updated if multiple grabbers are
    //   present. 
    if (!_fli->setGrabber(listOfGrabbers[0])) { 
        std::cout << "Error with Frame Grabber.";
        exit(1);
     }
    // modes are serial only, full, or grabber only
    _fli->setMode(FliSdk::Mode::Full);
    // add ourselves to the list of observers to be notified when there's
    //   a new image.
    _fli->addRawImageReceivedObserver(this);
    // update our handler
    _fli->update();

    uint16_t size1[3] = {640, 512, 0};
    uint16_t size2[3] = {1, 0, 0};
    // make the shm for the image
    shm_Open(&img, "IMG.im.shm", "TrackCamIMG", MAX_PIX, size1, 2,
        1);

    // make the shm for the non-destructive reads
    shm_Open(&ndr, "DNDR.im.shm", "TrackCamDNDR", 1, size2,
        1, 1);

    // make the shm for the exposure time
    shm_Open(&exposure, "DEXPOSURE.im.shm", "TrackCamDEXPOSURE", 1, size2,
        1, 10);

    // make the shm for the temperature
    shm_Open(&temp, "DTEMP.im.shm", "TrackCamDTEMP", 1, size2, 1, 10);

    // start the FG
    _fli->start();

}

/*
 * This is the function that is called when an updated image is available.
 */
void ImageReceiver::imageReceived(const uint8_t* image){

    // first store time
    struct timespec time;
    timespec_get(&time, TIME_UTC);

    // check the size of this image
    uint16_t width;
    uint16_t height;
    _fli->getCurrentImageDimension(width, height);
        
    double new_temp;
    double new_exp;
    int new_ndr;
    
    // get the ndr
    _fli->credTwo()->getNbReadWoReset(new_ndr);

    // get temperature of the snake
    _fli->credTwo()->getTempSnake(new_temp);

    // get exposure time
    _fli->credTwo()->getTint(new_exp);

    size_t edit;
    edit = sizeof(img.mtdata.latime) + sizeof(img.mtdata.atime) + 
        sizeof(img.mtdata.cnt0);

    // update metadata for image size
    if ((img.mtdata.size[0] != width) | (img.mtdata.size[1] != height)) {
        img.mtdata.size[0] = width;
        img.mtdata.size[1] = height;
        img.mtdata.nel = width * height;
        edit += (sizeof(img.mtdata.size) + sizeof(img.mtdata.nel));
    }

    // update shared memories
    for (int i=0; i < 4; i++){
        shm *cur_shm;
        switch (i){
            case 0: cur_shm = &img;
            // we don't need to update size and nel for other shms so remake len
            case 1: cur_shm = &temp;
                edit = sizeof(img.mtdata.latime) + sizeof(img.mtdata.atime) + 
                  sizeof(img.mtdata.cnt0);
            case 2: cur_shm = &ndr;
            case 3: cur_shm = &exposure;
        }

        // update times and count in metadata
        cur_shm->mtdata.atime = time;
        cur_shm->mtdata.latime = time;
        cur_shm->mtdata.cnt0++;

        // get the shm lock
        sem_wait(cur_shm->lock);
        // copy the updated metadata
        memcpy(cur_shm->shm + LATIME_OFFSET, &cur_shm->mtdata.latime, edit);
        // copy the data. 
        switch (i){
            case 0:
                memcpy(cur_shm->shm + IMAGE_OFFSET, image, cur_shm->mtdata.nel);
            case 1:
                memcpy(cur_shm->shm + IMAGE_OFFSET, &new_temp, sizeof(new_temp));
            case 2:
                memcpy(cur_shm->shm + IMAGE_OFFSET, &new_ndr, sizeof(uint8_t));
            case 3:
                memcpy(cur_shm->shm + IMAGE_OFFSET, &new_exp, sizeof(new_exp));
        }
        // release the shm lock
        sem_post(cur_shm->lock);
        // update all the semaphore
        sem_post(cur_shm->sem);
    }
}

/*
 * This method lets the FG know when we should be passed an updated image.
 *   0 means "as fast as possible".
 */
uint16_t ImageReceiver::fpsTrigger(){ return 0; }
