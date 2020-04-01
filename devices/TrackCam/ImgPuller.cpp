/*
This is a C++ script to update the tracking camera shared memory as a new
    image becomes available.

It Combines the First Light Imaging SDK with the ImageStreamIO library from
    the Multi-purpose Imaging Libraries toolKit (milk) group. Based on the
    ImCreat_img.c example in ImageStreamIO repo.

Note: C++ is used so we can take advantage of the IRawImageReceivedObserver
    class in the C++ FLI SDK.
*/

// Note, since this system may be handled by someone more familiar with python
//   than c/c++, I've tried to comment more extensively

#include <stdlib>          // include for malloc and exiting
#include <iostream>        // add for stdout writing

#include "FliSdk.h"        // compile with $FLISDK_DIR/include
#include "ImageStreamIO.h" // https://github.com/milk-org/ImageStreamIO
#include "ImageStruct.h"   // from ImageStremIO repo

class ImageReceiver : public IRawImageReceivedObserver{

    ImageReceiver();

    virtual void imageReceived(uint8_t* image) override;
    //do I need to override fpsTrigger?

  private:
    FliSdk* _fli;
    IMAGE imarray;     // pointer to array of images 
    long naxis = 2;    // number of axes
    uint8_t atype = 1; // data type (see ImageStruct.h for coding)
    uint32_t *imsize;  // image size
    int shared = 1;    // boolean for whether image in shared memory
    int NBkw = 2;      // number of keywords supported (length, width)
}

int main(){

    ImageReceiver();

}

void ImageReceiver::ImageReceiver(){

    _fli = new FliSdk();

    // get all the available grabbers
    std::vector<std::string> listOfGrabbers = _fli->detectGrabbers();

    // if there's at least one grabber
    if(listofCameras.size()){
       // connect to first grabber in the list
       // NOTE: this script needs to be updated if multiple grabbers are
       //   present. 
       _fli->setGrabber(listOfGrabbers[0]);
       // modes are serial only, full, or grabber only
       // TODO: confirm that get image size works on grab only mode
       _fli->setMode(FliSdk::Mode::GrabOnly);
       // update our handler
       _fli->update();
    } else {
        cout << "No camera detected. Check connection.";
        exit(EXIT_FAILURE);
    }
    
    // since imsize depends on naxis and is not known at compile time,
    //   we need to reserve memory with malloc
    imsize = (uint32_t *) malloc(sizeof(uint32_t)*naxis);
    // get the image size
    _fli->getCurrentImageDimension(imsize[0], imsize[1])

    // create an image in shared memory
    // last param is image type, see ImageStruct.h for more options.
    ImageStreamIO_createIm_gpu(&imarray, SHMNAME, naxis, imsize, atype, -1, 
        shared, IMAGE_NB_SEMPAHORE, NBkw, CIRCULAR_BUFFER);

    // since we are done with imsize, we have to free the memory we reserved
    free(imsize);

    _fli->addRawImageReceivedObserver(this);
}

void ImageReceiver::imageReceived(uint8_t* image){

    lock.acquire()

    // ImageStreamIO has a writing flag that should be used. We need to use
    //   a semaphore as well incase programs not using ISIO are accessing the
    //   shared memory
    imarray.md->write = 1;

    

    lock.release()
}
