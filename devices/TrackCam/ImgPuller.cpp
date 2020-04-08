/*
 * This is a C++ script to update the tracking camera shared memory as a new
 *    image becomes available.
 * 
 * It Combines the First Light Imaging SDK with the ImageStreamIO library from
 *    the Multi-purpose Imaging Libraries toolKit (milk) group. Based on the
 *    ImCreat_img.c example in ImageStreamIO repo.
 * 
 * Note: C++ is used so we can take advantage of the IRawImageReceivedObserver
 *    class in the C++ FLI SDK.
 *
 * TODO: Currently, a simple mutex lock is used to regulate resource access.
 *   This is done because the speeds seem to imply that nothing more is needed.
 *    If a speed up is desired, however, this can be changed to a more complex
 *    system which allows multiple readers to access the resource at once, while
 *    writer access locks the resource from any other readers/writers. 
 *
 *
 * Compiling:
 *    To compile use "g++ ImgPuller.cpp -I/$FLISDK_DIR/include -lpthread"
 *       g++ is a C++ compiler, -I includes directores, -lpthread is needed
 *       for semaphore use.
 */

// Note, since this system may be handled by someone more familiar with python
//   than c/c++, I've tried to comment more extensively

#include <stdlib>        // for malloc/calloc and exit
#include <semaphore.h>   // adds POSIX semaphores
#include <fcntl.h>       // adds O tags (O_CREAT)
#include <sys/stat.h>    // adds POSIX mode constants
#include <time.h>        // for getting the current time for timestamps
#include <sys/mman.h>    // for mmap
#include <sstream>       // for stringstream (to name semaphores)
#include <cstring>       // for strcpy
#include <fstream>       // for file reading/writing
#include <iostream>      // for cout (print)
using namespace std;

#include "FliSdk.h"      // compile with $FLISDK_DIR/include
#include "MetaStruct.h"  // a custom structure to store metadata

// define file names and directories for easier creating/access
#define SHM_DIR  "/tmp/shm/TrackCam/"
#define FNAME    SHM_DIR "IMG.im.shm"
#define SEMNAME  "/TrackCamIMG_"

// store offsets in metadata for easier access
// THESE NEED TO BE CHANGED IF IM_METADATA IS CHANGED
#define IMAGE_OFFSET   152
#define LATIME_OFFSET  96
#define ATIME_OFFSET   112
#define CNT0_OFFSET    128
#define SIZE_OFFSET    140
#define NEL_OFFSET     136

// define constants for camera
#define MAX_PIX 327680 // this is 640X512 resolution

/*
 * This is a class from the FLI SDK. Using it, we can create something that
 *    listens for when a new image is available.
 */
class ImageReceiver : public IRawImageReceivedObserver{

    // call the constructor
    ImageReceiver();

    // this is the method that handles when an image comes in
    virtual void imageReceived(uint8_t* image) override;
    // this method lets the FG know when to update us
    virtual double fpsTrigger() override;

// our private variables
  private:
    FliSdk* _fli;       // the handler of the FG and camera
    im_metadata mtdata; // our custom metadata struct
    
}

/*
 * Every C/C++ script has a main method. This is what is actually run when
 *    a compiled script is ran.
 */
int main(){

    // instantiate our class, which handles everything else.
    ImageReceiver* handler = new ImageReceiver();

}

/*
 * Here we define our classes' constructor, which includes setup.
 */
void ImageReceiver::ImageReceiver(){

    // instantiate a new FG/camera handler
    _fli = new FliSdk();

    // get all the available grabbers
    std::vector<std::string> listOfGrabbers = _fli->detectGrabbers();

    // if there are no grabbers
    if(!listofGrabbers.size()){
        cout << "No camera detected. Check connection.";
        exit(1);
    }

    // connect to first grabber in the list
    // NOTE: this script needs to be updated if multiple grabbers are
    //   present. 
    if (!_fli->setGrabber(listOfGrabbers[0])) { 
        cout << "Error with Frame Grabber.";
        exit(1)
     }
    // modes are serial only, full, or grabber only
    // TODO: confirm that get image size works on grab only mode
    _fli->setMode(FliSdk::Mode::GrabOnly);
    // update our handler
    _fli->update();
    
    // add ourselves to the list of observers to be notified when there's
    //   a new image.
    _fli->addRawImageReceivedObserver(this);

    // now that the FG is ready to be started, we set up the mmap and sems
    char* map; // the mmap region

    // First we check if there is already a shm set up
    FILE* backing = fopen(FNAME, "r");

    if (backing){ // This is the case where a shm exists, so read it
        // we need write/read access for mmap, so reopen file
        fclose(backing);
        backing = fopen(FNAME, "wb+");

        // mmap the file
        map = (char*) mmap(0, IMAGE_OFFSET+MAX_PIX, PROT_READ | PROT_WRITE,
            MAP_SHARED, fileno(backing), 0);

        // load in the metadata
        fread(&mtdata, IMAGE_OFFSET, 1, backing);

        // mmap creates a copy of the file so we can close our copy now.
        fclose(backing);
    } else { // This is the case where no shm exists, so make it
        // here we need to create the metadata
        strcpy(mtdata.name, "CRED2 Raw Image");
        mtdata.nel = MAX_PIX;
        mtdata.size[0] = 640;
        mtdata.size[1] = 512;
        mtdata.size[2] = 0;
        mtdata.naxis = 2;
        mtdata.dtype = 1;
        mtdata.semNb = 2;
        timespec_get(&mtdata.crtime, TIME_UTC);
        timespec_get(&mtdata.latime, TIME_UTC);
        timespec_get(&mtdata.atime, TIME_UTC);

        // now we create a place-holder for the image
        uint8_t img [MAX_PIX];

        // now we create the file and write in this info
        backing = fopen(FNAME, "wb+");
        fwrite(&mtdata, sizeof(im_metadata), 1, backing);
        fwrite(&img, sizeof(img), 1, backing);
        
        // now we can open the mmap
        map = (char*) mmap(0, IMAGE_OFFSET+MAX_PIX, PROT_READ | PROT_WRITE,
            MAP_SHARED, fileno(backing), 0);

        // mmap creates a copy of the file so we can close our copy now.
        fclose(backing);
    }

    // make the semaphores.
    stringstream name;
    name << SEMNAME << "lock";
    // the O_CREAT flag on POSIX semaphores will connect if the semaphore
    // already exists, and create it if it doesn't
    sem_t* lock = sem_open(lname.str().c_str(), O_CREAT, 0644, 1);
    if (lock == SEM_FAILED) { cout << "Semaphore failure.\n"; exit(1); }

    // to reset a string stream, set the underlying string to empty and clear
    // any error messages.
    name.str("");
    name.clear()
    
    /*
     * Here we need to malloc/calloc since we don't know how many semaphores
     *   there will be. BUT, since this list of semaphores is persistent, this
     *   memory is never freed. For new C/C++ programmers: when you use malloc
     *   or calloc to allocate memory, there should usually be a corresponding
     *   call to free. Whether this practice should be maintained for variables
     *   persistent through execution is a discussion, but it seems like the
     *   answer is that, so long as you're operating on a modern OS, the memory
     *   will be freed automatically upon program termination.
     */
    sem_t* sems = (sem_t*) calloc(mtdata.semNb, sizeof(sem_t));
    for (int i = 0; i < mtdata.semNb; i++) {
        if (i < 10) { name << SEMNAME << "sem0" << i; }   
        else { name << SEMNAME << "sem" << i; }
        sems[i] = sem_open(name.str().c_str(), O_CREAT, 0644, 0);
        if (sems[i] == SEM_FAILED) { cout << "Semaphore failure.\n"; exit(1); }
    } 

    // start the FG
    _fli->start();
}

/*
 * This is the function that is called when an updated image is available.
 */
void ImageReceiver::imageReceived(uint8_t* image){

    lock.acquire()

    // ImageStreamIO has a writing flag that should be used. We need to use
    //   a semaphore as well incase programs not using ISIO are accessing the
    //   shared memory
    imarray.md->write = 1;

    

    lock.release()
}

/*
 * This methods lets the FG know when we should be passed an updated image.
 *   0 means "as fast as possible".
 */
double ImageReceiver::fpsTrigger(){ return 0 }
